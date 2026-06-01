const buttons = Array.from(document.querySelectorAll(".mode-button"));
const answerEl = document.querySelector("#answer");
const statusEl = document.querySelector("#status");
const activeModeEl = document.querySelector("#active-mode");
const questionEl = document.querySelector("#question");
const submitEl = document.querySelector("#submit");
const sampleEl = document.querySelector("#sample");

let activeMode = "agent_v2";

const labels = {
  agent_v2: "ReAct Agent V2",
  agent_v1: "ReAct Agent V1",
  chatbot: "Chatbot Baseline",
  mock: "Mock Demo",
};

buttons.forEach((button) => {
  button.addEventListener("click", () => {
    activeMode = button.dataset.mode;
    buttons.forEach((item) => item.classList.toggle("active", item === button));
    activeModeEl.textContent = labels[activeMode];
  });
});

sampleEl.addEventListener("click", () => {
  questionEl.value = "Can I buy 5 MacBooks with the STUDENT coupon and ship them to Danang? Include the final cost.";
});

submitEl.addEventListener("click", async () => {
  const question = questionEl.value.trim();
  if (!question) {
    answerEl.textContent = "Please enter a question first.";
    return;
  }

  setStatus("Running", "loading");
  answerEl.textContent = "Calling selected mode...";
  submitEl.disabled = true;

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: activeMode, question }),
    });

    const payload = await response.json();
    if (!response.ok) {
      answerEl.textContent = `${payload.message || "Request failed"}\n\n${payload.detail || ""}`.trim();
      setStatus("API error", "loading");
      return;
    }

    answerEl.textContent = payload.answer;
    setStatus("Done", "ok");
  } catch (error) {
    answerEl.textContent = `Request failed.\n\n${error}`;
    setStatus("Error", "loading");
  } finally {
    submitEl.disabled = false;
  }
});

function setStatus(text, state) {
  statusEl.textContent = text;
  statusEl.className = `status-pill ${state || ""}`.trim();
}
