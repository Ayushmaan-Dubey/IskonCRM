document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('form[data-prevent-double-submit]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      if (form.dataset.submitted === 'true') {
        event.preventDefault();
        return false;
      }

      form.dataset.submitted = 'true';
      window.setTimeout(function () {
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (button) {
          button.disabled = true;
          if (button.tagName === 'BUTTON') {
            button.dataset.originalText = button.textContent;
            button.textContent = 'Saving...';
          }
        });
      }, 0);
      return true;
    });
  });
});
