// This is composer dictation, not the realtime two-way AI companion.
// Uses the browser SpeechRecognition API when available. Never sends a chat message.
const dictateButton = document.getElementById("dictation-toggle");
const dictationFeedback = document.getElementById("dictation-feedback");
const dictationInput = document.getElementById("message-input");
const dictationComposer = document.getElementById("composer");
const dictationAuthModal = document.getElementById("auth-modal");
const dictationLivePanel = document.getElementById("companion-panel");
const SpeechApi = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognizer = null;
let stopping = false;
let originalDraft = "";
let noticeTimeout;

function setDictationUI(isListening) {
  dictateButton.classList.toggle("listening", isListening);
  dictateButton.setAttribute("aria-pressed", String(isListening));
  dictateButton.setAttribute("aria-label", isListening ? "Stop dictation" : "Start dictation");
  dictateButton.title = isListening ? "Stop dictation" : "Dictate into message";
}
function dictationNotice(message, persistent = false) {
  clearTimeout(noticeTimeout);
  dictationFeedback.textContent = message;
  dictationFeedback.hidden = false;
  if (!persistent) noticeTimeout = setTimeout(() => { dictationFeedback.hidden = true; }, 5500);
}
function resetDictation(instance) {
  if (recognizer !== instance) return;
  recognizer = null;
  stopping = false;
  setDictationUI(false);
  if (dictationFeedback.textContent === "Listening…") dictationFeedback.hidden = true;
}
function stopDictation(abort = false) {
  if (!recognizer || stopping) return;
  stopping = true;
  setDictationUI(false);
  dictationFeedback.hidden = true;
  try {
    if (abort) recognizer.abort();
    else recognizer.stop();
  } catch {
    resetDictation(recognizer);
  }
}
function beginDictation() {
  if (recognizer) {
    stopDictation();
    return;
  }
  if (!dictationAuthModal.hidden) {
    dictationNotice("Sign in before using dictation.");
    return;
  }
  if (!dictationLivePanel.hidden) {
    dictationNotice("End the live voice conversation before dictating a message.");
    return;
  }
  if (dictationInput.disabled) {
    dictationNotice("Wait until the current message finishes.");
    return;
  }
  if (!SpeechApi) {
    dictationNotice("Speech-to-text is not supported by this browser. Try an up-to-date Chrome or Edge browser.");
    return;
  }
  const instance = new SpeechApi();
  recognizer = instance;
  stopping = false;
  originalDraft = dictationInput.value;
  instance.continuous = true;
  instance.interimResults = true;
  instance.lang = navigator.language || "en-US";
  instance.onstart = () => {
    if (recognizer === instance && !stopping) {
      setDictationUI(true);
      dictationNotice("Listening…", true);
    }
  };
  instance.onresult = (event) => {
    if (recognizer !== instance) return;
    const fragments = [];
    for (let index = 0; index < event.results.length; index++) {
      const phrase = event.results[index][0]?.transcript?.trim();
      if (phrase) fragments.push(phrase);
    }
    const said = fragments.join(" ").trim();
    if (!said) return;
    const separator = originalDraft && !/\s$/.test(originalDraft) ? " " : "";
    const limit = dictationInput.maxLength > 0 ? dictationInput.maxLength : Infinity;
    dictationInput.value = (originalDraft + separator + said).slice(0, limit);
    dictationInput.dispatchEvent(new Event("input", { bubbles: true }));
  };
  instance.onerror = (event) => {
    if (recognizer !== instance) return;
    if (event.error === "aborted") return;
    if (event.error === "no-speech") {
      dictationNotice("No speech detected. Tap the mic to try again.");
    } else if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      dictationNotice("Microphone or speech recognition permission was denied.");
    } else {
      dictationNotice("Dictation stopped: " + String(event.error || "recognition failed"));
    }
  };
  instance.onend = () => {
    resetDictation(instance);
  };
  try {
    instance.start();
    setDictationUI(true);
    dictationNotice("Listening…", true);
  } catch {
    resetDictation(instance);
    dictationNotice("Couldn't start dictation. Check microphone permissions.");
  }
}

dictateButton.addEventListener("click", beginDictation);
// Dictation inserts editable text and NEVER automatically submits a message.
dictationComposer.addEventListener("submit", () => stopDictation(true));
dictationInput.addEventListener("keydown", () => { if (recognizer && !stopping) stopDictation(); });
window.addEventListener("dragonzpyder:live-start", () => stopDictation(true));
window.addEventListener("dragonzpyder:logout", () => stopDictation(true));
window.addEventListener("pagehide", () => stopDictation(true));
