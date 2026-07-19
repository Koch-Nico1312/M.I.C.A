const MICA_BASE_URL = "http://127.0.0.1:8000";

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "send-page-to-mica",
    title: "Seite an M.I.C.A senden",
    contexts: ["page", "selection", "link"],
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  const stored = await chrome.storage.local.get(["micaSessionId", "jarvisSessionId"]);
  const payload = {
    title: tab?.title || "Browser capture",
    kind: "note",
    content: [
      `URL: ${info.linkUrl || tab?.url || ""}`,
      info.selectionText ? `Selection: ${info.selectionText}` : "",
    ].filter(Boolean).join("\n"),
    user: "u-admin",
  };

  await chrome.storage.local.set({
    lastMicaTab: tab?.url || "",
    lastMicaSelection: info.selectionText || "",
    lastMicaCaptureAt: new Date().toISOString(),
  });

  try {
    await fetch(`${MICA_BASE_URL}/api/platform/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "create_artifact",
        payload: { ...payload, companion_session_id: stored.micaSessionId || stored.jarvisSessionId || "" },
      }),
    });
  } catch (error) {
    await chrome.storage.local.set({ lastMicaError: String(error) });
  }
});
