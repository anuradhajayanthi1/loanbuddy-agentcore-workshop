// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
/* LoanBuddy SPA - deliberately framework-free and build-free.
 *
 * Auth flow (Lab 1's teaching aid): Cognito USER_PASSWORD_AUTH from the
 * browser -> access token (JWT) -> Authorization: Bearer on every agent
 * call. Open dev tools and watch it. There is no backend server here: the
 * token goes straight from Cognito to the AgentCore Runtime's JWT
 * authorizer (via a same-origin CloudFront proxy that exists only to avoid
 * browser CORS).
 */
"use strict";
const C = window.LOANBUDDY;

const $ = (id) => document.getElementById(id);
const messagesEl = $("messages");

// Surface ANY script error on the login panel instead of failing silently.
window.addEventListener("error", (e) => {
  const el = $("login-error");
  if (el) { el.textContent = "Script error: " + e.message; el.hidden = false; }
});
window.addEventListener("unhandledrejection", (e) => {
  const el = $("login-error");
  if (el) { el.textContent = "Error: " + (e.reason && e.reason.message || e.reason); el.hidden = false; }
});

let accessToken = null;
let username = null;

function newSessionId() {
  // Runtime requires 33+ chars.
  const rand = (crypto.randomUUID && crypto.randomUUID()) ||
    Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, "0")).join("");
  return "lb-" + rand + "-" + Date.now().toString(36);
}

// Runtime session id: survives reloads within a browser session (short-term
// context), but a NEW session id after logout or a new day is the point of
// Lab 2 - continuity must come from Memory + the ledger, not this id.
// (sessionStorage can throw under strict privacy settings - degrade to
// per-load sessions rather than dying before the login handler attaches.)
let sessionId;
try {
  sessionId = sessionStorage.getItem("lb-session") || newSessionId();
  sessionStorage.setItem("lb-session", sessionId);
} catch (_) {
  sessionId = newSessionId();
}

/* ---------------- Cognito ---------------- */

async function login(user, pass) {
  const resp = await fetch(`https://cognito-idp.${C.region}.amazonaws.com/`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-amz-json-1.1",
      "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth",
    },
    body: JSON.stringify({
      AuthFlow: "USER_PASSWORD_AUTH",
      ClientId: C.spaClientId,
      AuthParameters: { USERNAME: user, PASSWORD: pass },
    }),
  });
  const data = await resp.json();
  if (!resp.ok) throw new Error(data.message || data.__type || "Login failed");
  if (!data.AuthenticationResult) throw new Error("Unexpected auth challenge: " + data.ChallengeName);
  return data.AuthenticationResult.AccessToken;
}

/* ---------------- Agent invocation ---------------- */

async function invokeAgent(prompt) {
  if (!C.agentArnEncoded) {
    return "(The LoanBuddy agent isn't deployed yet - that's Lab 1. " +
           "This UI is live and you're authenticated; the brain is missing.)";
  }
  // Straight from the browser to the Runtime's front door - the AgentCore
  // data plane supports CORS, so no backend and no proxy sit in between.
  // (Long tool calls - document vision, underwriting - can exceed proxy
  // timeouts; a direct call just waits.)
  const url = `https://bedrock-agentcore.${C.region}.amazonaws.com` +
              `/runtimes/${C.agentArnEncoded}/invocations?qualifier=DEFAULT`;
  const resp = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${accessToken}`,
      "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": sessionId,
    },
    body: JSON.stringify({ prompt }),
  });
  if (resp.status === 401 || resp.status === 403) {
    throw new Error(`Rejected by the Runtime's JWT authorizer (${resp.status}). ` +
                    "Token expired? Sign out and back in.");
  }
  if (!resp.ok) throw new Error(`Agent call failed: ${resp.status} ${await resp.text()}`);

  const ctype = resp.headers.get("content-type") || "";
  if (ctype.includes("text/event-stream")) {
    // Streaming responses arrive as SSE data: lines.
    const chunks = [];
    for (const line of (await resp.text()).split("\n")) {
      if (line.startsWith("data:")) {
        try { chunks.push(JSON.parse(line.slice(5))); }
        catch { chunks.push(line.slice(5).trim()); }
      }
    }
    return chunks.join("");
  }
  const body = await resp.text();
  try { return JSON.parse(body); } catch { return body; }
}

/* ---------------- Upload handling ----------------
 * The agent's reply carries a presigned PUT URL (from its
 * request_upload_url tool). We detect it, offer a file picker, PUT the
 * file browser-side (the doc goes straight to S3 - never through the
 * agent), then tell the agent the s3_key so it can run analyze_document.
 */
// Match presigned URLs in either signature style (SigV4: X-Amz-Signature,
// SigV2: AWSAccessKeyId + Signature).
const UPLOAD_URL_RE = /https:\/\/[^\s"'<>]+(?:X-Amz-Signature|AWSAccessKeyId)=[^\s"'<>)*\]]+/;
let pendingUpload = null;

function scanForUpload(text) {
  const m = text.match(UPLOAD_URL_RE);
  if (!m) return text;
  const url = m[0];
  const path = new URL(url).pathname;               // /docs/{sub}/{type}-{id}.png
  const s3Key = decodeURIComponent(path.replace(/^\//, ""));
  const docType = (s3Key.match(/docs\/[^/]+\/([a-z_]+)-/) || [])[1] || "document";
  pendingUpload = { url, s3Key, docType };
  $("upload-label").textContent = `Upload your ${docType.replace("_", " ")}:`;
  $("upload-strip").hidden = false;
  // The raw presigned URL is machine plumbing - hide it from the human.
  return text.replace(url, "[secure upload link ready - use the upload panel below]");
}

async function doUpload() {
  const file = $("file-input").files[0];
  if (!file || !pendingUpload) return;
  $("upload-progress").textContent = "Uploading…";
  const resp = await fetch(pendingUpload.url, {
    method: "PUT",
    headers: { "Content-Type": "image/png" },
    body: file,
  });
  if (!resp.ok) {
    $("upload-progress").textContent = `Upload failed (${resp.status}).`;
    return;
  }
  $("upload-progress").textContent = "";
  $("upload-strip").hidden = true;
  const key = pendingUpload.s3Key;
  pendingUpload = null;
  await send(`I've uploaded the document. Its s3_key is ${key}. Please analyze it.`);
}

/* ---------------- Status chip ----------------
 * Workshop-grade: the chip reflects status words the agent uses in
 * conversation. Ground truth lives in the DynamoDB ledger (Lab 2 has you
 * look at the real record).
 */
function scanForStatus(text) {
  const m = text.match(/\b(STARTED|DOCS_PENDING|UNDER_REVIEW|DECISION)\b/);
  if (m) $("status-chip").textContent = m[1].replace("_", " ");
}

/* ---------------- Chat plumbing ---------------- */

function addMsg(kind, text) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${kind}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

let busy = false;
async function send(text) {
  if (busy || !text.trim()) return;
  busy = true; $("send-btn").disabled = true;
  addMsg("user", text);
  const thinking = addMsg("agent", "");
  thinking.classList.add("thinking");
  try {
    const reply = String(await invokeAgent(text));
    thinking.classList.remove("thinking");
    thinking.textContent = scanForUpload(reply);   // scrubs raw upload URLs
    scanForStatus(reply);
  } catch (err) {
    thinking.classList.remove("thinking");
    thinking.closest(".msg").className = "msg system";
    thinking.textContent = String(err.message || err);
  } finally {
    busy = false; $("send-btn").disabled = false;
  }
}

/* ---------------- Wiring ---------------- */

// Deployment badge - so you always know WHICH bank you're talking to.
if (C.badge && !C.badge.startsWith("REPLACED_BY")) {
  $("login-badge").textContent = C.badge;
  $("header-badge").textContent = C.badge;
}

$("login-btn").addEventListener("click", async () => {
  $("login-error").hidden = true;
  const btn = $("login-btn");
  btn.disabled = true;
  btn.textContent = "Signing in…";
  try {
    username = $("username").value.trim();
    if (!username || !$("password").value) {
      throw new Error("Enter a username and password (see your workshop card).");
    }
    accessToken = await login(username, $("password").value);
    $("login-panel").hidden = true;
    $("chat-panel").hidden = false;
    $("who").textContent = username;
    addMsg("system", "Signed in. Your identity now rides every request as a JWT.");
    send("Hello!");
  } catch (err) {
    $("login-error").textContent = String(err.message || err);
    $("login-error").hidden = false;
  } finally {
    btn.disabled = false;
    btn.textContent = "Sign in";
  }
});
$("password").addEventListener("keydown", (e) => { if (e.key === "Enter") $("login-btn").click(); });

$("logout-btn").addEventListener("click", () => {
  accessToken = null;
  try {
    sessionStorage.removeItem("lb-session");
    sessionId = newSessionId();
    sessionStorage.setItem("lb-session", sessionId);
  } catch (_) { /* strict privacy mode */ }
  location.reload();
});

$("send-btn").addEventListener("click", () => {
  const t = $("prompt").value; $("prompt").value = ""; send(t);
});
$("prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    $("send-btn").click();
  }
});
$("upload-btn").addEventListener("click", doUpload);
$("upload-cancel").addEventListener("click", () => { $("upload-strip").hidden = true; });
