document.addEventListener("DOMContentLoaded", () => {
  const photo = document.querySelector("[data-crop-preview]");
  if (!photo) return;
  const fields = ["position_x", "position_y", "zoom"].map(name => document.getElementById("id_" + name));
  const update = () => {
    const [x, y, zoom] = fields.map(input => Number(input.value.replace(",", ".")));
    const position = `${Math.max(0, Math.min(100, x))}% ${Math.max(0, Math.min(100, y))}%`;
    photo.style.objectPosition = position;
    photo.style.transformOrigin = position;
    photo.style.transform = `scale(${Math.max(1, Math.min(3, zoom || 1))})`;
  };
  fields.forEach(input => input.addEventListener("input", update));
  update();
});
