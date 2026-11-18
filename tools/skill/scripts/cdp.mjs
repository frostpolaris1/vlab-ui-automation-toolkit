// Minimal RFC6455 WebSocket + CDP client for reading the user's Edge devtools endpoint.
// Used ONLY for observation/understanding of the experiment page, not for injection.
import net from "node:net";
import crypto from "node:crypto";
import http from "node:http";

export function connectWS(wsUrl) {
  return new Promise((resolve, reject) => {
    const u = new URL(wsUrl);
    const key = crypto.randomBytes(16).toString("base64");
    const sock = net.connect({ host: u.hostname, port: Number(u.port || 80) }, () => {
      sock.write(
        `GET ${u.pathname}${u.search} HTTP/1.1\r\n` +
        `Host: ${u.host}\r\n` +
        `Upgrade: websocket\r\n` +
        `Connection: Upgrade\r\n` +
        `Sec-WebSocket-Key: ${key}\r\n` +
        `Sec-WebSocket-Version: 13\r\n\r\n`
      );
    });
    let handshakeDone = false;
    let buf = Buffer.alloc(0);
    const listeners = new Set();
    let fragBuf = [];
    let settled = false;

    function emit(text) { for (const l of listeners) { try { l(text); } catch {} } }
    function sendFrame(opcode, payload) {
      const mask = crypto.randomBytes(4);
      const len = payload.length;
      let header;
      if (len < 126) {
        header = Buffer.from([0x80 | opcode, 0x80 | len]);
      } else if (len < 65536) {
        header = Buffer.alloc(4);
        header[0] = 0x80 | opcode; header[1] = 0x80 | 126;
        header.writeUInt16BE(len, 2);
      } else {
        header = Buffer.alloc(10);
        header[0] = 0x80 | opcode; header[1] = 0x80 | 127;
        header.writeBigUInt64BE(BigInt(len), 2);
      }
      const masked = Buffer.alloc(len);
      for (let i = 0; i < len; i++) masked[i] = payload[i] ^ mask[i % 4];
      sock.write(Buffer.concat([header, mask, masked]));
    }
    function handleFrame(fin, opcode, payload) {
      if (opcode === 0x8) { sock.end(); return; }
      if (opcode === 0x9) { sendFrame(0xA, payload); return; }
      if (opcode === 0xA) return;
      if (opcode === 0x1 || opcode === 0x2) {
        if (fin) emit(payload.toString("utf8"));
        else { fragBuf = [payload]; }
      } else if (opcode === 0x0) {
        fragBuf.push(payload);
        if (fin) { emit(Buffer.concat(fragBuf).toString("utf8")); fragBuf = []; }
      }
    }
    function parse() {
      for (;;) {
        if (buf.length < 2) return;
        const fin = (buf[0] & 0x80) !== 0;
        const opcode = buf[0] & 0x0f;
        const masked = (buf[1] & 0x80) !== 0;
        let len = buf[1] & 0x7f;
        let off = 2;
        if (len === 126) { if (buf.length < 4) return; len = buf.readUInt16BE(2); off = 4; }
        else if (len === 127) { if (buf.length < 10) return; len = Number(buf.readBigUInt64BE(2)); off = 10; }
        let maskKey = null;
        if (masked) { if (buf.length < off + 4) return; maskKey = buf.subarray(off, off + 4); off += 4; }
        if (buf.length < off + len) return;
        let payload = buf.subarray(off, off + len);
        if (maskKey) { payload = Buffer.from(payload); for (let i = 0; i < len; i++) payload[i] ^= maskKey[i % 4]; }
        buf = buf.subarray(off + len);
        handleFrame(fin, opcode, payload);
      }
    }
    sock.on("data", (d) => {
      buf = Buffer.concat([buf, d]);
      if (!handshakeDone) {
        const idx = buf.indexOf("\r\n\r\n");
        if (idx === -1) return;
        const head = buf.subarray(0, idx).toString();
        if (!/HTTP\/1\.1 101/.test(head)) {
          settled = true;
          reject(new Error("ws handshake failed: " + head.split("\r\n")[0]));
          sock.destroy();
          return;
        }
        handshakeDone = true;
        buf = buf.subarray(idx + 4);
        settled = true;
        resolve(api);
      }
      parse();
    });
    sock.on("error", (e) => { if (!settled) { settled = true; reject(e); } });
    const api = {
      send(text) { sendFrame(0x1, Buffer.from(text, "utf8")); },
      onMessage(fn) { listeners.add(fn); return () => listeners.delete(fn); },
      close() { try { sendFrame(0x8, Buffer.alloc(0)); } catch {} sock.end(); },
    };
  });
}

export async function connectCDP(wsUrl) {
  const ws = await connectWS(wsUrl);
  let nextId = 1;
  const pending = new Map();
  const eventHandlers = new Set();
  ws.onMessage((text) => {
    let msg;
    try { msg = JSON.parse(text); } catch { return; }
    if (msg.id !== undefined && pending.has(msg.id)) {
      const { resolve, reject, timer } = pending.get(msg.id);
      pending.delete(msg.id);
      clearTimeout(timer);
      if (msg.error) reject(new Error(method0(msg) + ": " + JSON.stringify(msg.error)));
      else resolve(msg.result);
    } else if (msg.method) {
      for (const h of eventHandlers) { try { h(msg); } catch {} }
    }
  });
  function method0() { return "CDP error"; }
  return {
    send(method, params = {}, sessionId) {
      const id = nextId++;
      const msg = { id, method, params };
      if (sessionId) msg.sessionId = sessionId;
      ws.send(JSON.stringify(msg));
      return new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
          if (pending.has(id)) { pending.delete(id); reject(new Error("CDP timeout: " + method)); }
        }, 25000);
        pending.set(id, { resolve, reject, timer });
      });
    },
    onEvent(fn) { eventHandlers.add(fn); return () => eventHandlers.delete(fn); },
    close() { ws.close(); },
  };
}

export async function listTargets(port = 9333) {
  const body = await new Promise((resolve, reject) => {
    http.get(`http://127.0.0.1:${port}/json`, (r) => {
      let d = "";
      r.on("data", (c) => (d += c));
      r.on("end", () => resolve(d));
    }).on("error", reject);
  });
  return JSON.parse(body);
}

// One-shot helper: connect to a page target, run fn(cdp), always close.
export async function withPage(targetId, fn, port = 9333) {
  const targets = await listTargets(port);
  const t = targets.find((x) => x.id === targetId);
  if (!t) throw new Error("target not found: " + targetId);
  const cdp = await connectCDP(t.webSocketDebuggerUrl);
  try {
    return await fn(cdp, t);
  } finally {
    cdp.close();
  }
}

// Evaluate JS in page and return the value (observation only).
export async function evaluate(cdp, expression) {
  const r = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (r.exceptionDetails) throw new Error("page eval exception: " + JSON.stringify(r.exceptionDetails).slice(0, 500));
  return r.result ? r.result.value : undefined;
}