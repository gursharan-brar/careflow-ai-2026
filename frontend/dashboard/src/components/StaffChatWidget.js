import { useEffect, useRef, useState } from "react";

const API_URL = process.env.REACT_APP_API_URL;

const GREETING =
  "Hi! I'm the CareFlow AI staff assistant. I can help explain features or draft notes — I don't have live data lookup in this build.";
const NETWORK_ERROR_REPLY = "Sorry, I couldn't reach the server just now. Please try again.";

export default function StaffChatWidget() {
  const [open, setOpen] = useState(false);
  const [greeted, setGreeted] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const historyRef = useRef([]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function openPanel() {
    setOpen(true);
    if (!greeted) {
      setMessages([{ role: "assistant", content: GREETING }]);
      setGreeted(true);
    }
  }

  async function sendMessage(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) {
      return;
    }

    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setSending(true);

    try {
      const response = await fetch(`${API_URL}/api/chat/staff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ message, history: historyRef.current }),
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = await response.json();
      historyRef.current = [
        ...historyRef.current,
        { role: "user", content: message },
        { role: "assistant", content: data.reply },
      ];
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: NETWORK_ERROR_REPLY }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => (open ? setOpen(false) : openPanel())}
        aria-label="Open staff assistant"
        className="fixed bottom-5 right-5 w-14 h-14 rounded-full bg-c-teal text-white shadow-lg flex items-center justify-center hover:bg-c-teal-hover z-50"
      >
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
      </button>

      {open && (
        <div className="fixed bottom-24 right-5 w-80 h-[28rem] bg-white rounded-2xl shadow-2xl flex flex-col overflow-hidden z-50 border border-gray-100">
          <div className="bg-c-navy text-white px-4 py-3 flex items-center justify-between">
            <div>
              <p className="font-semibold text-sm">CareFlow AI Staff Assistant</p>
              <p className="text-xs text-white/70">Internal use only</p>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="text-white/80 hover:text-white text-lg leading-none px-1"
            >
              &times;
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3 bg-gray-50 space-y-2">
            {messages.map((m, i) => (
              <div
                key={i}
                className={`max-w-[85%] px-3 py-2 rounded-xl text-sm whitespace-pre-wrap break-words ${
                  m.role === "user"
                    ? "bg-c-teal text-white ml-auto"
                    : "bg-white border border-gray-200 text-c-text mr-auto"
                }`}
              >
                {m.content}
              </div>
            ))}
            {sending && (
              <div className="max-w-[85%] px-3 py-2 rounded-xl text-sm bg-white border border-gray-200 text-gray-400 mr-auto">
                ...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form onSubmit={sendMessage} className="flex gap-2 p-2 border-t border-gray-100">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type a message..."
              disabled={sending}
              className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-c-teal"
            />
            <button
              type="submit"
              disabled={sending}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-c-teal text-white hover:bg-c-teal-hover disabled:bg-c-teal/50"
            >
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}
