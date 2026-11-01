/* ReSOURCE: Независимые расходы рейсового прихода перед обычной проверкой средней себестоимости; доставка рейса не дублируется. */
(() => {
  "use strict";
  document.querySelectorAll("[data-independent-expenses]").forEach((form) => {
    const list = form.querySelector("[data-independent-expense-list]");
    const template = form.querySelector("[data-independent-expense-template]");
    form.querySelector("[data-add-independent-expense]")?.addEventListener("click", () => {
      list.append(template.content.cloneNode(true));
      list.lastElementChild.querySelector("input").focus();
    });
  });
})();
