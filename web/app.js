const buttons = Array.from(document.querySelectorAll(".mode-button"));
const answerEl = document.querySelector("#answer");
const statusEl = document.querySelector("#status");
const activeModeEl = document.querySelector("#active-mode");
const questionEl = document.querySelector("#question");
const submitEl = document.querySelector("#submit");
const sampleStockEl = document.querySelector("#sample-stock");
const sampleHeavyEl = document.querySelector("#sample-heavy");
const traceListEl = document.querySelector("#trace-list");
const productGridEl = document.querySelector("#product-grid");

let activeMode = "mock";

const labels = {
  mock: "Mock Demo",
  agent_v2: "ReAct Agent V2",
  agent_v1: "ReAct Agent V1",
  chatbot: "Chatbot Baseline",
};

buttons.forEach((button) => {
  button.addEventListener("click", () => {
    activeMode = button.dataset.mode;
    buttons.forEach((item) => item.classList.toggle("active", item === button));
    activeModeEl.textContent = labels[activeMode];
  });
});

sampleStockEl.addEventListener("click", () => {
  questionEl.value = "Can I buy 5 MacBooks with the STUDENT coupon and ship them to Danang? Include the final cost.";
});

sampleHeavyEl.addEventListener("click", () => {
  questionEl.value = "I want to buy 1 standing desk with coupon VIP and ship it to Ho Chi Minh. What is the final total?";
});

submitEl.addEventListener("click", async () => {
  const question = questionEl.value.trim();
  if (!question) {
    answerEl.textContent = "Please enter a question first.";
    return;
  }

  setStatus("Running", "loading");
  answerEl.textContent = "Calling selected mode...";
  renderTrace([]);
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
      renderTrace([
        {
          step: 1,
          thought: "API request failed.",
          action: "Use Mock Demo",
          observation: "Gemini quota or high demand is likely when the status is 429 or 503.",
        },
      ]);
      setStatus("API error", "error");
      return;
    }

    answerEl.textContent = payload.answer;
    renderTrace(payload.trace || []);
    setStatus("Done", "ok");
  } catch (error) {
    answerEl.textContent = `Request failed.\n\n${error}`;
    renderTrace([]);
    setStatus("Error", "error");
  } finally {
    submitEl.disabled = false;
  }
});

loadDataset();

async function loadDataset() {
  try {
    const response = await fetch("/api/dataset");
    const payload = await response.json();
    document.querySelector("#product-count").textContent = payload.counts.products;
    document.querySelector("#coupon-count").textContent = payload.counts.coupons;
    document.querySelector("#city-count").textContent = payload.counts.shipping_cities;
    document.querySelector("#tool-count").textContent = payload.counts.tools;
    document.querySelector("#coupon-list").textContent = payload.coupons.join(", ");
    document.querySelector("#city-list").textContent = payload.shipping_cities.join(", ");
    renderProducts(payload.products || []);
  } catch (error) {
    productGridEl.innerHTML = `<div class="trace-empty">Dataset failed to load.</div>`;
  }
}

function renderProducts(products) {
  productGridEl.innerHTML = products
    .map(
      (product) => `
        <article class="product-card">
          <strong>${escapeHtml(product.display_name)}</strong>
          <span>${escapeHtml(product.category)} · key: ${escapeHtml(product.key)}</span>
          <div class="product-meta">
            <div>$${Number(product.price_usd).toFixed(2)}</div>
            <div>${Number(product.weight_kg)}kg</div>
            <div>stock ${Number(product.stock)}</div>
          </div>
        </article>
      `,
    )
    .join("");
}

function renderTrace(trace) {
  if (!trace.length) {
    traceListEl.innerHTML = '<li class="trace-empty">No trace yet.</li>';
    return;
  }

  traceListEl.innerHTML = trace
    .map(
      (item) => `
        <li>
          <div class="trace-step">
            <span>Step ${escapeHtml(String(item.step))}</span>
            <span>Thought → Action → Observation</span>
          </div>
          <dl>
            <dt>Thought</dt>
            <dd>${escapeHtml(item.thought || "")}</dd>
            <dt>Action</dt>
            <dd>${escapeHtml(item.action || "")}</dd>
            <dt>Observation</dt>
            <dd>${escapeHtml(item.observation || "")}</dd>
          </dl>
        </li>
      `,
    )
    .join("");
}

function setStatus(text, state) {
  statusEl.textContent = text;
  statusEl.className = `status-pill ${state || ""}`.trim();
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
