/**
 * Process group DOM utilities (no store/state)
 */
import { store as preferencesStore } from "/components/sidebar/bottom/preferences/preferences-store.js";

export async function applyModeSteps(
  detailMode,
  showUtils,
  chatHistory = document.getElementById("chat-history"),
) {
  const mode =
    detailMode ||
    preferencesStore.detailMode ||
    "current";

  if (!chatHistory) return;

  chatHistory.dataset.detailMode = mode;

  const shouldExpand = mode !== "collapsed";
  const allMode = mode === "expanded";
  const showUtilsFlag =
    typeof showUtils === "boolean"
      ? showUtils
      : preferencesStore.showUtils || false;
  const pending = [];
  const messages = Array.from(chatHistory.querySelectorAll(".process-group"));
  const windowEnd = Number(chatHistory.dataset.messageWindowEnd);
  const windowTotal = Number(chatHistory.dataset.messageWindowTotal);
  const isAtTail =
    Number.isFinite(windowEnd) &&
    Number.isFinite(windowTotal) &&
    windowEnd >= windowTotal;
  for (let i = 0; i < messages.length; i += 1) {
    const group = messages[i];
    if (typeof group.__setExpanded === "function") {
      pending.push(Promise.resolve(group.__setExpanded(shouldExpand)));
    } else {
      group.classList.toggle("expanded", shouldExpand);
    }

    const steps = Array.from(group.querySelectorAll(".process-step"));
    const isComplete =
      group.hasAttribute("data-group-complete") ||
      Boolean(group.querySelector(".process-group-response"));
    let currentStep = null;
    if (
      mode === "current" &&
      isAtTail &&
      group === messages[messages.length - 1] &&
      !isComplete
    ) {
      for (let si = steps.length - 1; si >= 0; si -= 1) {
        if (
          showUtilsFlag ||
          !steps[si].classList.contains("message-util")
        ) {
          currentStep = steps[si];
          break;
        }
      }
    }

    for (let si = 0; si < steps.length; si += 1) {
      const step = steps[si];
      const shouldExpandStep = allMode || step === currentStep;
      if (typeof step.__setExpanded === "function") {
        pending.push(Promise.resolve(step.__setExpanded(shouldExpandStep)));
      } else {
        step.classList.toggle("expanded", shouldExpandStep);
      }
    }
  }

  await Promise.allSettled(pending);
}
