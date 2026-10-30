(() => {
  'use strict';
  const header = document.querySelector('[data-adaptive-navigation]');
  if (!header) return;
  const nav = header.querySelector('[data-desktop-navigation]');
  const overflow = header.querySelector('[data-nav-overflow]');
  const moreButton = overflow.querySelector('button');
  const overflowList = overflow.querySelector('.nav-overflow-list');
  const items = Array.from(nav.children).filter(item => item !== overflow);
  const drawer = header.querySelector('.navigation-drawer');
  const mobileNav = drawer.querySelector('[data-mobile-navigation]');
  const utilities = header.querySelector('[data-header-utilities]');
  const tools = header.querySelector('.session-tools');
  const mobileButton = header.querySelector('.mobile-nav-toggle');
  const profile = header.querySelector('[data-header-profile]');
  const profileButton = profile.querySelector('.profile-toggle');
  const profileMenu = profile.querySelector('.header-profile-menu');
  const mobile = window.matchMedia('(max-width: 760px)');
  let frame = null;

  const setMore = open => {
    moreButton.setAttribute('aria-expanded', String(open));
    overflowList.hidden = !open;
  };
  const setProfile = open => {
    profileButton.setAttribute('aria-expanded', String(open));
    profileMenu.hidden = !open;
  };
  items.forEach((item, index) => {
    item.dataset.navItem = '';
    const trigger = item.matches('a') ? item : item.querySelector('.nav-dropdown-trigger');
    if (trigger.classList.contains('active')) {
      header.querySelector('[data-mobile-section]').textContent = trigger.textContent.trim();
    }
    const menu = item.querySelector('.nav-dropdown-menu');
    if (!menu) return;
    menu.id = `navigation-section-${index}`;
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'nav-section-toggle';
    toggle.setAttribute('aria-label', `Подразделы: ${trigger.textContent.trim()}`);
    toggle.setAttribute('aria-controls', menu.id);
    const expanded = trigger.classList.contains('active');
    toggle.setAttribute('aria-expanded', String(expanded));
    item.classList.toggle('nav-section-open', expanded);
    toggle.innerHTML = '<span aria-hidden="true">⌄</span>';
    trigger.after(toggle);
    toggle.addEventListener('click', () => {
      const open = toggle.getAttribute('aria-expanded') !== 'true';
      toggle.setAttribute('aria-expanded', String(open));
      item.classList.toggle('nav-section-open', open);
    });
  });

  const resetDrawerState = () => {
    mobileButton.setAttribute('aria-expanded', 'false');
    document.documentElement.classList.remove('navigation-drawer-open');
  };
  const closeDrawer = () => {
    if (drawer.open) drawer.close();
    resetDrawerState();
  };
  const layout = () => {
    frame = null;
    const focused = header.contains(document.activeElement) ? document.activeElement : null;
    const restoreFocus = () => {
      if (!focused || focused === document.activeElement) return;
      if (focused.getClientRects().length) focused.focus({preventScroll: true});
      else if (mobile.matches) mobileButton.focus({preventScroll: true});
      else if (overflowList.contains(focused) && !overflow.hidden) moreButton.focus({preventScroll: true});
      else if (profile.contains(focused)) profileButton.focus({preventScroll: true});
    };
    if (mobile.matches) {
      setMore(false);
      overflow.hidden = true;
      items.forEach(item => { if (item.parentElement !== mobileNav) mobileNav.append(item); });
      const mobileUtilities = drawer.querySelector('[data-mobile-utilities]');
      if (utilities.parentElement !== mobileUtilities) mobileUtilities.append(utilities);
      // Профиль в выдвижной панели доступен сразу, без второго меню.
      profileMenu.hidden = false;
      restoreFocus();
      return;
    }
    closeDrawer();
    if (utilities.parentElement !== tools) {
      tools.insertBefore(utilities, mobileButton);
      setProfile(false);
    }
    // Измеряем все исходные пункты в одной строке, включая место для «Ещё».
    // Перемещаются исходные узлы: права, формы и обработчики не дублируются.
    items.forEach(item => { if (item.parentElement !== nav) nav.insertBefore(item, overflow); });
    overflow.hidden = false;
    const widths = items.map(item => item.getBoundingClientRect().width);
    const available = nav.getBoundingClientRect().width;
    const total = widths.reduce((sum, width) => sum + width, 0);
    let visible = items.length;
    if (total > available) {
      const moreWidth = overflow.getBoundingClientRect().width;
      let used = 0;
      visible = 0;
      while (visible < items.length && used + widths[visible] + moreWidth <= available) {
        used += widths[visible++];
      }
    }
    items.slice(visible).forEach(item => overflowList.append(item));
    overflow.hidden = visible === items.length;
    moreButton.classList.toggle('has-active-section', items.slice(visible).some(item =>
      (item.matches('a') ? item : item.querySelector('.nav-dropdown-trigger')).classList.contains('active')));
    if (overflow.hidden) setMore(false);
    restoreFocus();
  };
  const schedule = () => {
    if (frame === null) frame = window.requestAnimationFrame(layout);
  };
  moreButton.addEventListener('click', () => {
    const open = moreButton.getAttribute('aria-expanded') !== 'true';
    setProfile(false);
    setMore(open);
  });
  profileButton.addEventListener('click', () => {
    const open = profileButton.getAttribute('aria-expanded') !== 'true';
    setMore(false);
    setProfile(open);
  });
  mobileButton.addEventListener('click', () => {
    if (drawer.open) return closeDrawer();
    drawer.showModal();
    mobileButton.setAttribute('aria-expanded', 'true');
    document.documentElement.classList.add('navigation-drawer-open');
  });
  drawer.querySelector('[data-close-navigation]').addEventListener('click', closeDrawer);
  drawer.addEventListener('close', resetDrawerState);
  drawer.addEventListener('cancel', event => {
    event.preventDefault();
    closeDrawer();
  });
  drawer.addEventListener('click', event => {
    if (event.target !== drawer) return;
    const box = drawer.getBoundingClientRect();
    if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) closeDrawer();
  });
  document.addEventListener('click', event => {
    if (!overflow.contains(event.target)) setMore(false);
    if (!profile.contains(event.target) && !mobile.matches) setProfile(false);
  });
  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape') return;
    if (moreButton.getAttribute('aria-expanded') === 'true') {
      setMore(false);
      moreButton.focus();
      event.preventDefault();
    }
    if (profileButton.getAttribute('aria-expanded') === 'true') {
      setProfile(false);
      profileButton.focus();
      event.preventDefault();
    }
  });
  // Закрытое меню не должно удерживать фокус на невидимом элементе при Tab.
  overflow.addEventListener('focusout', () => {
    window.setTimeout(() => { if (!overflow.contains(document.activeElement)) setMore(false); }, 0);
  });
  profile.addEventListener('focusout', () => {
    window.setTimeout(() => { if (!profile.contains(document.activeElement) && !mobile.matches) setProfile(false); }, 0);
  });
  window.addEventListener('resize', schedule);
  mobile.addEventListener('change', schedule);
  const observer = new ResizeObserver(schedule);
  observer.observe(nav);
  observer.observe(tools);
  if (document.fonts) {
    document.fonts.ready.then(schedule);
    document.fonts.addEventListener('loadingdone', schedule);
  }
  layout();
})();
