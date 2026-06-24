(function () {
  const API_URL = "";
  const SESSION_STORAGE_KEY = "careflow_patient_chat_session_id";
  const GREETING = "Hi! I'm the CareFlow AI assistant. I can help with how check-in works, what to expect, and where to find your wait time. I can't give medical advice — for symptoms, please use the check-in and health questions flow.";
  const NETWORK_ERROR_REPLY = "Sorry, I couldn't reach the server just now. Please check your connection and try again.";

  const params = new URLSearchParams(window.location.search);
  const visitId = params.get("visit_id");

  function getSessionId() {
    if (visitId) {
      return null;
    }
    let sessionId = localStorage.getItem(SESSION_STORAGE_KEY);
    if (!sessionId) {
      sessionId = (Date.now().toString(36) + Math.random().toString(36).slice(2));
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    }
    return sessionId;
  }

  const sessionId = getSessionId();
  const history = [];

  const launcher = document.createElement("button");
  launcher.id = "careflow-chat-launcher";
  launcher.type = "button";
  launcher.setAttribute("aria-label", "Open chat assistant");
  launcher.setAttribute("data-tooltip", "Ask CareFlow AI");
  launcher.innerHTML = '<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>';

  const panel = document.createElement("div");
  panel.id = "careflow-chat-panel";
  panel.innerHTML =
    '<div id="careflow-chat-header">' +
      '<div>CareFlow AI Assistant<span class="subtitle">General questions &amp; check-in help</span>' +
        '<span id="careflow-chat-online"><span class="careflow-chat-dot"></span>Online</span>' +
      '</div>' +
      '<button type="button" id="careflow-chat-close" aria-label="Close chat">&times;</button>' +
    "</div>" +
    '<div id="careflow-chat-messages"></div>' +
    '<form id="careflow-chat-form">' +
      '<input type="text" id="careflow-chat-input" placeholder="Type a message..." autocomplete="off">' +
      '<button type="submit" id="careflow-chat-send">Send</button>' +
    "</form>";

  document.body.appendChild(launcher);
  document.body.appendChild(panel);

  const messagesEl = panel.querySelector("#careflow-chat-messages");
  const formEl = panel.querySelector("#careflow-chat-form");
  const inputEl = panel.querySelector("#careflow-chat-input");
  const sendBtn = panel.querySelector("#careflow-chat-send");
  const closeBtn = panel.querySelector("#careflow-chat-close");

  function addMessage(role, content) {
    const msg = document.createElement("div");
    msg.className = `careflow-chat-msg ${role}`;
    msg.textContent = content;
    messagesEl.appendChild(msg);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return msg;
  }

  let greeted = false;

  function openPanel() {
    panel.classList.add("open");
    launcher.classList.add("careflow-chat-launcher-active");
    if (!greeted) {
      addMessage("assistant", GREETING);
      greeted = true;
    }
    inputEl.focus();
  }

  function closePanel() {
    panel.classList.remove("open");
    launcher.classList.remove("careflow-chat-launcher-active");
  }

  launcher.addEventListener("click", () => {
    if (panel.classList.contains("open")) {
      closePanel();
    } else {
      openPanel();
    }
  });

  closeBtn.addEventListener("click", closePanel);

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();

    const message = inputEl.value.trim();
    if (!message) {
      return;
    }

    addMessage("user", message);
    inputEl.value = "";
    inputEl.disabled = true;
    sendBtn.disabled = true;

    const pending = addMessage("pending", "...");

    try {
      const response = await fetch(`${API_URL}/api/chat/patient`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history,
          visit_id: visitId || undefined,
          session_id: sessionId || undefined,
        }),
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = await response.json();
      pending.remove();
      addMessage("assistant", data.reply);

      history.push({ role: "user", content: message });
      history.push({ role: "assistant", content: data.reply });
    } catch (err) {
      pending.remove();
      addMessage("assistant", NETWORK_ERROR_REPLY);
    } finally {
      inputEl.disabled = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  });
})();
