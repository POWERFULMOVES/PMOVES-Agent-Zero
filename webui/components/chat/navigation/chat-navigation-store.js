import { createStore } from "/js/AlpineStore.js";
import {
    getMessageWindowState,
    loadAdjacentMessageWindow,
    scrollMessageWindowToEdge,
} from "/js/messages.js";

const model = {
    // Configuration
    scrollMargin: 60,
    prevTolerance: 35,
    nextTolerance: 5,

    init() {
        // Any initialization if needed
    },

    async scrollToTop() {
        await scrollMessageWindowToEdge("start");
    },

    async scrollToBottom() {
        await scrollMessageWindowToEdge("end");
    },

    async scrollToPrevUserMessage() {
        const scroller = this._getChatHistoryEl();
        if (!scroller) return;

        const positions = this._getUserMessagePositions(scroller);
        const scrollerRect = scroller.getBoundingClientRect();

        const prevThreshold = this.scrollMargin - this.prevTolerance; // 25px

        const currentIndex = positions.findIndex((p) => {
            const relativeTop = p.el.getBoundingClientRect().top - scrollerRect.top;
            return relativeTop >= prevThreshold;
        });

        if (currentIndex > 0) {
            // Go to previous message
            positions[currentIndex - 1].el.scrollIntoView({ block: "start", behavior: "smooth" });
        } else if (currentIndex === 0) {
            if (getMessageWindowState().hasOlder) {
                await loadAdjacentMessageWindow("older");
                this._scrollToLastUserAboveThreshold(scroller, prevThreshold);
            } else {
                scroller.scrollTo({ top: 0, behavior: "instant" });
            }
        } else if (currentIndex === -1 && positions.length > 0) {
            // All messages are above the threshold (scrolled past), scroll to bottom
            positions[positions.length - 1].el.scrollIntoView({ block: "start", behavior: "smooth" });
        } else if (positions.length === 0 && getMessageWindowState().hasOlder) {
            await loadAdjacentMessageWindow("older");
            this._scrollToLastUserAboveThreshold(scroller, prevThreshold);
        }
    },

    async scrollToNextUserMessage() {
        const scroller = this._getChatHistoryEl();
        if (!scroller) return;

        const positions = this._getUserMessagePositions(scroller);
        const scrollerRect = scroller.getBoundingClientRect();

        const nextThreshold = this.scrollMargin + this.nextTolerance; // 65px

        // Find first message below the threshold
        const targetIndex = positions.findIndex((p) => {
            const relativeTop = p.el.getBoundingClientRect().top - scrollerRect.top;
            return relativeTop > nextThreshold;
        });

        if (targetIndex !== -1) {
            // Go to that message
            positions[targetIndex].el.scrollIntoView({ block: "start", behavior: "smooth" });
        } else {
            if (getMessageWindowState().hasNewer) {
                await loadAdjacentMessageWindow("newer");
                this._scrollToFirstUserBelowThreshold(scroller, nextThreshold);
            } else {
                await this.scrollToBottom();
            }
        }
    },

    _scrollToLastUserAboveThreshold(scroller, threshold) {
        const scrollerRect = scroller.getBoundingClientRect();
        const positions = this._getUserMessagePositions(scroller);
        const candidates = positions.filter(
            ({ el }) => el.getBoundingClientRect().top - scrollerRect.top < threshold
        );
        candidates.at(-1)?.el.scrollIntoView({ block: "start", behavior: "smooth" });
    },

    _scrollToFirstUserBelowThreshold(scroller, threshold) {
        const scrollerRect = scroller.getBoundingClientRect();
        const target = this._getUserMessagePositions(scroller).find(
            ({ el }) => el.getBoundingClientRect().top - scrollerRect.top > threshold
        );
        target?.el.scrollIntoView({ block: "start", behavior: "smooth" });
    },

    // Helpers
    _getChatHistoryEl() {
        return document.getElementById("chat-history");
    },

    _getUserMessagePositions(scroller) {
         const userMessageEls = Array.from(
            scroller.querySelectorAll(".message-container.user-container")
          );
          // Helper for getElementTopInScroller
          const getTop = (el) => {
              const elRect = el.getBoundingClientRect();
              const scrollerRect = scroller.getBoundingClientRect();
              return elRect.top - scrollerRect.top + scroller.scrollTop;
          };

          return userMessageEls
            .map((el) => ({ el, top: getTop(el) }))
            .sort((a, b) => a.top - b.top);
    }
};

const store = createStore("chatNavigation", model);
export { store };
