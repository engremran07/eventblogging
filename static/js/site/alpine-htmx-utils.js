/**
 * =============================================================================
 * ALPINE + HTMX INTEGRATION UTILITIES
 * =============================================================================
 * 
 * Reusable utilities for Alpine.js and HTMX integration.
 * Provides common patterns for:
 *  - Form validation and submission
 *  - Dynamic content loading
 *  - State synchronization
 *  - Component interaction
 */

(function () {
  "use strict";

  /**
   * ===========================================================================
   * FORM UTILITIES
   * ===========================================================================
   */

  /**
   * Validate a form field using HTML5 validation
   * @param {HTMLElement} field - Form field element
   * @returns {boolean} - True if valid
   */
  function validateField(field) {
    if (!field.checkValidity) {
      return true;
    }

    const isValid = field.checkValidity();

    if (!isValid) {
      field.classList.add("is-invalid");
      field.setAttribute("aria-invalid", "true");
    } else {
      field.classList.remove("is-invalid");
      field.setAttribute("aria-invalid", "false");
    }

    return isValid;
  }

  /**
   * Validate entire form
   * @param {HTMLFormElement} form - Form element
   * @returns {boolean} - True if all fields are valid
   */
  function validateForm(form) {
    const fields = form.querySelectorAll(
      "input, textarea, select"
    );
    let isValid = true;

    fields.forEach((field) => {
      if (!validateField(field)) {
        isValid = false;
      }
    });

    return isValid;
  }

  /**
   * Handle form field validation on input/change
   * @param {HTMLFormElement} form - Form element
   */
  function setupFormValidation(form) {
    const fields = form.querySelectorAll(
      "input, textarea, select"
    );

    fields.forEach((field) => {
      field.addEventListener("blur", () => validateField(field));
      field.addEventListener("change", () => validateField(field));
      field.addEventListener("input", () => {
        // Clear error state on input
        field.classList.remove("is-invalid");
      });
    });
  }

  /**
   * Submit form with optional validation
   * @param {HTMLFormElement} form - Form to submit
   * @param {Object} options - Options object
   */
  function submitForm(form, options = {}) {
    const {
      validate = true,
      showLoading = true,
      onSuccess = null,
      onError = null,
    } = options;

    if (validate && !validateForm(form)) {
      return;
    }

    if (showLoading) {
      const submitButton = form.querySelector(
        'button[type="submit"]'
      );
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.classList.add("is-loading");
      }
    }

    const formData = new FormData(form);
    const method = form.getAttribute("method") || "POST";
    const action = form.getAttribute("action") || window.location.href;

    htmx.ajax(method, action, {
      data: formData,
      target: form.getAttribute("data-target") || form,
      swap: form.getAttribute("data-swap") || "outerHTML",
      onSuccess: onSuccess,
      onError: onError,
    });
  }

  /**
   * ===========================================================================
   * MODAL UTILITIES
   * ===========================================================================
   */

  /**
   * Show modal with optional content loading
   * @param {string} modalId - ID of modal element
   * @param {string} url - Optional URL to load content from
   * @param {Object} options - Additional options
   */
  function showModal(modalId, url = null, options = {}) {
    const modal = document.getElementById(modalId);
    if (!modal) {
      console.warn(`Modal not found: ${modalId}`);
      return;
    }

    if (url) {
      const contentArea = modal.querySelector(
        "[data-modal-content]"
      );
      if (contentArea) {
        htmx.ajax("GET", url, contentArea);
      }
    }

    modal.classList.add("active");
    modal.showModal?.();

    if (options.onOpen) {
      options.onOpen(modal);
    }
  }

  /**
   * Hide modal
   * @param {string} modalId - ID of modal element
   * @param {Object} options - Additional options
   */
  function hideModal(modalId, options = {}) {
    const modal = document.getElementById(modalId);
    if (!modal) {
      console.warn(`Modal not found: ${modalId}`);
      return;
    }

    modal.classList.remove("active");
    modal.close?.();

    if (options.onClose) {
      options.onClose(modal);
    }
  }

  /**
   * ===========================================================================
   * SEARCH/FILTER UTILITIES
   * ===========================================================================
   */

  /**
   * Debounce function for search/filter inputs
   * @param {Function} fn - Function to debounce
   * @param {number} delay - Delay in milliseconds
   * @returns {Function} - Debounced function
   */
  function debounce(fn, delay = 300) {
    let timeoutId;
    return function (...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
  }

  /**
   * Setup autocomplete/search field
   * @param {HTMLInputElement} field - Input field element
   * @param {string} url - URL to fetch suggestions from
   * @param {Object} options - Additional options
   */
  function setupAutocomplete(field, url, options = {}) {
    const {
      minChars = 2,
      maxResults = 10,
      onSelect = null,
    } = options;

    const debouncedSearch = debounce((query) => {
      if (query.length < minChars) {
        return;
      }

      const params = new URLSearchParams({ q: query });
      htmx.ajax("GET", `${url}?${params}`, {
        target: `#${field.id}-results`,
        swap: "innerHTML",
      });
    }, 300);

    field.addEventListener("input", (e) => {
      debouncedSearch(e.target.value);
    });
  }

  /**
   * ===========================================================================
   * TABLE/LIST UTILITIES
   * ===========================================================================
   */

  /**
   * Setup row selection with checkboxes
   * @param {string} tableSelector - CSS selector for table
   */
  function setupRowSelection(tableSelector) {
    const table = document.querySelector(tableSelector);
    if (!table) return;

    const selectAllCheckbox = table.querySelector(
      'input[name="select-all"]'
    );
    const rowCheckboxes = table.querySelectorAll(
      'input[name="select-row"]'
    );

    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener("change", (e) => {
        rowCheckboxes.forEach((checkbox) => {
          checkbox.checked = e.target.checked;
          checkbox
            .closest("tr")
            ?.classList.toggle("selected", e.target.checked);
        });
      });
    }

    rowCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", (e) => {
        e.target
          .closest("tr")
          ?.classList.toggle("selected", e.target.checked);

        // Update select-all checkbox state
        if (selectAllCheckbox) {
          selectAllCheckbox.checked = 
            Array.from(rowCheckboxes).every(
              (cb) => cb.checked
            );
        }
      });
    });
  }

  /**
   * ===========================================================================
   * NOTIFICATION UTILITIES
   * ===========================================================================
   */

  /**
   * Show notification message
   * @param {string} message - Message text
   * @param {string} level - Level (success, info, warning, error)
   * @param {number} duration - Auto-dismiss duration in ms
   */
  function showNotification(message, level = "info", duration = 5000) {
    const container =
      document.querySelector("[data-notifications]") ||
      document.body;

    const notification = document.createElement("div");
    notification.className = `notification notification-${level}`;
    notification.setAttribute("role", "alert");
    notification.innerHTML = `
      <div class="notification-content">
        <span class="notification-message">${message}</span>
        <button class="notification-close" aria-label="Close">
          <span>&times;</span>
        </button>
      </div>
    `;

    container.appendChild(notification);

    const closeButton = notification.querySelector(".notification-close");
    closeButton.addEventListener("click", () => {
      notification.classList.add("notification-dismiss");
      setTimeout(() => notification.remove(), 300);
    });

    if (duration > 0) {
      setTimeout(() => {
        notification.classList.add("notification-dismiss");
        setTimeout(() => notification.remove(), 300);
      }, duration);
    }
  }

  /**
   * ===========================================================================
   * EXPORT UTILITIES
   * ===========================================================================
   */

  window.alpineHtmxUtils = {
    // Form
    validateField,
    validateForm,
    setupFormValidation,
    submitForm,

    // Modal
    showModal,
    hideModal,

    // Search
    debounce,
    setupAutocomplete,

    // Table
    setupRowSelection,

    // Notifications
    showNotification,
  };

  /**
   * ===========================================================================
   * AUTO-INITIALIZATION
   * ===========================================================================
   */

  document.addEventListener("DOMContentLoaded", () => {
    // Setup form validation for all forms with data-validate attribute
    document.querySelectorAll("form[data-validate]").forEach((form) => {
      setupFormValidation(form);
    });

    // Setup row selection for all tables with data-selectable attribute
    document.querySelectorAll("table[data-selectable]").forEach((table) => {
      setupRowSelection(`#${table.id || "table"}`);
    });

    // Setup autocomplete for all inputs with data-autocomplete attribute
    document.querySelectorAll("input[data-autocomplete]").forEach((field) => {
      const url = field.getAttribute("data-autocomplete");
      setupAutocomplete(field, url);
    });
  });

  // Re-initialize when HTMX adds new items
  htmx.on("htmx:afterSwap", () => {
    document
      .querySelectorAll("form[data-validate]:not([data-validated])")
      .forEach((form) => {
        setupFormValidation(form);
        form.setAttribute("data-validated", "true");
      });
  });
})();
