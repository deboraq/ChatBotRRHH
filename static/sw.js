self.addEventListener("push", function (event) {
  let data = {};
  try {
    data = event.data.json();
  } catch (_) {
    data = { title: "Panel de atención", body: event.data ? event.data.text() : "" };
  }
  const title = data.title || "Panel de atención";
  const options = {
    body: data.body || "",
    tag: data.tag || "rrhh-push",
    renotify: true,
    data: { url: data.url || "/rrhh" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || "/rrhh";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (clientList) {
      for (const client of clientList) {
        if (client.url.includes("/rrhh") && "focus" in client) return client.focus();
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
