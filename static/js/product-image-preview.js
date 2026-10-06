(() => {
  "use strict";

  const links = document.querySelectorAll("[data-product-title-image]");
  if (!links.length) return;

  const preview = document.createElement("div");
  preview.className = "product-title-hover-preview";
  preview.hidden = true;
  const image = document.createElement("img");
  image.alt = "";
  preview.append(image);
  document.body.append(preview);

  let active = null;

  function position(clientX, clientY) {
    const gap = 14;
    const width = preview.offsetWidth || 260;
    const height = preview.offsetHeight || 260;
    const left = Math.min(clientX + gap, window.innerWidth - width - gap);
    const top = Math.min(clientY + gap, window.innerHeight - height - gap);
    preview.style.left = `${Math.max(gap, left)}px`;
    preview.style.top = `${Math.max(gap, top)}px`;
  }

  function show(target, event) {
    const source = target.dataset.productTitleImage;
    if (!source) return;
    active = target;
    image.src = source;
    preview.hidden = false;
    if (event && Number.isFinite(event.clientX)) {
      position(event.clientX, event.clientY);
    } else {
      const rect = target.getBoundingClientRect();
      position(rect.right, rect.bottom);
    }
  }

  function hide(target) {
    if (active !== target) return;
    active = null;
    preview.hidden = true;
    image.removeAttribute("src");
  }

  image.addEventListener("error", () => {
    preview.hidden = true;
  });

  links.forEach((link) => {
    link.addEventListener("pointerenter", (event) => show(link, event));
    link.addEventListener("pointermove", (event) => {
      if (active === link) position(event.clientX, event.clientY);
    });
    link.addEventListener("pointerleave", () => hide(link));
    link.addEventListener("focus", () => show(link));
    link.addEventListener("blur", () => hide(link));
  });
})();
