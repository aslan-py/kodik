(() => {
  'use strict';

  const config = window.KODIK_ADMIN_UI;
  if (!config || !Array.isArray(config.sections)) return;

  const rootPath = `/${String(window.SERVER_URL || '/admin/api')
    .split('/')
    .filter(Boolean)
    .slice(0, -1)
    .join('/')}`;
  const modelSections = new Map();
  config.sections.forEach((section) => {
    section.models.forEach((model) => modelSections.set(model, section));
  });

  const combinedLocation = () =>
    `${window.location.pathname}${window.location.hash}`.toLowerCase();

  function menuItemByKey(key) {
    return [...document.querySelectorAll('[data-menu-id]')].find((item) =>
      String(item.dataset.menuId || '').endsWith(`-${key}`)
    );
  }

  function modelMenuItem(model) {
    return menuItemByKey(model);
  }

  function sectionMenuContainer(section) {
    return menuItemByKey(`section-${section.title}`)?.closest(
      '.ant-menu-submenu'
    );
  }

  function dashboardMenuItem() {
    return menuItemByKey('dashboard');
  }

  function replaceVisibleLabel(element, label) {
    if (!element) return;
    const leaves = [...element.querySelectorAll('*')].filter(
      (node) => node.children.length === 0 && node.textContent.trim()
    );
    const target = leaves.at(-1);
    if (target) {
      if (target.textContent !== label) target.textContent = label;
    } else if (element.textContent !== label) {
      element.textContent = label;
    }
    element.setAttribute('title', label);
    element.setAttribute('aria-label', label);
  }

  function markNavigation() {
    const dashboard = dashboardMenuItem();
    replaceVisibleLabel(dashboard, 'Пайплайн');
    if (dashboard) {
      dashboard.dataset.kodikZone = 'pipeline';
      dashboard.dataset.kodikSection = 'pipeline';
    }

    config.sections.forEach((section, sectionIndex) => {
      const target = sectionMenuContainer(section);
      if (target) {
        target.setAttribute('title', section.title);
        target.setAttribute('aria-label', section.title);
        target.dataset.kodikZone = section.zone;
        target.dataset.kodikSection = section.id;
        if (section.zone === 'settings') {
          const settings = config.sections.filter(
            (item) => item.zone === 'settings'
          );
          if (section.id === settings[0].id) target.dataset.kodikEdge = 'start';
          if (section.id === settings.at(-1).id)
            target.dataset.kodikEdge = 'end';
        }
        target.dataset.kodikOrder = String(sectionIndex);
      }
    });

    config.hiddenModels.forEach((model) => {
      const modelItem = modelMenuItem(model);
      const section = modelSections.get(model);
      const container =
        modelItem?.closest('.ant-menu-submenu, .ant-menu-item') ||
        (section ? sectionMenuContainer(section) : null);
      if (container) {
        container.dataset.kodikHidden = 'true';
        container.setAttribute('aria-hidden', 'true');
      }
    });
  }

  function currentSection() {
    const location = combinedLocation();
    for (const [model, section] of modelSections) {
      if (location.includes(model.toLowerCase())) return section;
    }
    const normalized = window.location.pathname.replace(/\/$/, '');
    if (
      normalized === rootPath.replace(/\/$/, '') &&
      ['', '#', '#/'].includes(window.location.hash)
    ) {
      return config.sections.find((section) => section.id === 'pipeline');
    }
    return null;
  }

  function contentContainer() {
    return (
      document.querySelector('.ant-layout-content') ||
      document.querySelector('main') ||
      document.querySelector('.ant-layout > .ant-card')
    );
  }

  function updateBanner() {
    const section = currentSection();
    const existing = document.querySelector('.kodik-section-banner');
    if (!section) {
      existing?.remove();
      return;
    }
    const content = contentContainer();
    if (!content) return;
    const banner = existing || document.createElement('section');
    if (!existing || existing.dataset.kodikSection !== section.id) {
      banner.className = 'kodik-section-banner';
      banner.dataset.kodikSection = section.id;
      banner.dataset.kodikZone = section.zone;
      banner.setAttribute('role', 'note');
      banner.setAttribute('aria-label', `Раздел: ${section.title}`);
      banner.innerHTML = '';
      const title = document.createElement('h2');
      title.className = 'kodik-section-banner__title';
      title.textContent = section.title;
      const description = document.createElement('p');
      description.className = 'kodik-section-banner__description';
      description.textContent = section.description;
      banner.append(title, description);
    }
    if (banner.parentElement !== content || content.firstElementChild !== banner) {
      content.prepend(banner);
    }
  }

  function renameDashboardHeading() {
    const section = currentSection();
    if (section?.id !== 'pipeline') return;
    document.querySelectorAll('h1, h2, .ant-page-header-heading-title').forEach(
      (heading) => {
        if (/^(dashboard|панель управления)$/i.test(heading.textContent.trim())) {
          heading.textContent = 'Пайплайн';
        }
      }
    );
  }

  let scheduled = false;
  const observerOptions = { childList: true, subtree: true };
  function applyUi() {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      const observer = window.__KODIK_ADMIN_OBSERVER__;
      observer?.disconnect();
      try {
        markNavigation();
        renameDashboardHeading();
        updateBanner();
      } finally {
        observer?.observe(document.documentElement, observerOptions);
      }
    });
  }

  if (!window.__KODIK_ADMIN_OBSERVER__) {
    window.__KODIK_ADMIN_OBSERVER__ = new MutationObserver(applyUi);
    window.__KODIK_ADMIN_OBSERVER__.observe(
      document.documentElement,
      observerOptions
    );
  }
  window.addEventListener('hashchange', applyUi);
  window.addEventListener('popstate', applyUi);
  applyUi();
})();
