import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";
import { store as sidebarStore } from "/components/sidebar/sidebar-store.js";

const PLUGIN_ID = "_pin_to_top";

const model = {
  pins: { chat: {}, task: {} },
  _initialized: false,

  async init() {
    if (this._initialized) return;
    this._initialized = true;

    for (const kind of ["chat", "task"]) {
      sidebarStore.registerRowListExtension(kind, PLUGIN_ID, {
        sort: (items) => this.sortItems(kind, items),
        dividerBefore: (item, index, items) =>
          this.dividerBefore(kind, item, index, items),
      });
    }

    await this.loadPins();
  },

  async loadPins() {
    try {
      const response = await callJsonApi(`/plugins/${PLUGIN_ID}/get_pins`, {});
      this.pins = {
        chat: { ...(response?.pins?.chat || {}) },
        task: { ...(response?.pins?.task || {}) },
      };
    } catch (error) {
      void toastFrontendError(error?.message || "Failed to load pinned items.", "Pin to Top");
    }
  },

  async toggleFromMenu(menuId, kind) {
    const itemId = this.itemIdFromMenu(menuId, kind);
    if (!itemId) return;

    try {
      const response = await callJsonApi(`/plugins/${PLUGIN_ID}/toggle_pin`, {
        kind,
        item_id: itemId,
      });
      const kindPins = { ...(this.pins[kind] || {}) };
      if (response?.pinned) kindPins[itemId] = response.timestamp;
      else delete kindPins[itemId];
      this.pins = { ...this.pins, [kind]: kindPins };
    } catch (error) {
      void toastFrontendError(error?.message || "Failed to update the pin.", "Pin to Top");
    }
  },

  itemIdFromMenu(menuId, kind) {
    const prefix = `${kind}:`;
    return typeof menuId === "string" && menuId.startsWith(prefix)
      ? menuId.slice(prefix.length)
      : "";
  },

  isMenuItemPinned(menuId, kind) {
    return this.isPinned(kind, this.itemIdFromMenu(menuId, kind));
  },

  isPinned(kind, itemId) {
    return Object.prototype.hasOwnProperty.call(this.pins[kind] || {}, itemId);
  },

  sortItems(kind, items) {
    const kindPins = this.pins[kind] || {};
    return items
      .map((item, index) => ({ item, index }))
      .sort((left, right) => {
        const leftPin = kindPins[left.item.id];
        const rightPin = kindPins[right.item.id];
        const leftPinned = leftPin !== undefined;
        const rightPinned = rightPin !== undefined;
        if (leftPinned !== rightPinned) return leftPinned ? -1 : 1;
        if (leftPinned && leftPin !== rightPin) return leftPin - rightPin;
        return left.index - right.index;
      })
      .map(({ item }) => item);
  },

  dividerBefore(kind, item, index, items) {
    return index > 0
      && !this.isPinned(kind, item.id)
      && this.isPinned(kind, items[index - 1]?.id);
  },
};

export const store = createStore("pinToTop", model);
