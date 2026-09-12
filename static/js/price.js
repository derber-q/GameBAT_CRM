document.addEventListener("DOMContentLoaded", () => {
  const form = document.querySelector("[data-retail-export]");
  if (!form || !window.fetch) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = form.querySelector("button[type='submit']");
    const result = form.querySelector("[data-retail-result]");
    button.disabled = true;
    result.textContent = "Формируем файл…";
    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
      });
      const contentType = response.headers.get("Content-Type") || "";
      if (!response.ok || !contentType.includes("spreadsheetml")) {
        throw new Error("Не удалось сформировать розничный прайс.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "resource-retail-price.xlsx";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      const skipped = Number(response.headers.get("X-ReSOURCE-Skipped-No-Price") || 0);
      result.textContent = skipped
        ? `Файл скачан. Не включено товаров без розничной цены: ${skipped}.`
        : "Файл скачан. Все товары с положительным остатком имеют розничную цену.";
    } catch (error) {
      result.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  });
});
