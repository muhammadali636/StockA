//DOM
document.addEventListener('DOMContentLoaded', function() {
  console.log("Global JS loaded!");

  //REG PAGE

  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    const registerPassword = document.getElementById('registerPassword');
    const toggleRegPassword = document.getElementById('toggleRegPassword');

    //pas show/hide
    if (toggleRegPassword) {
      toggleRegPassword.addEventListener('change', function() {
        registerPassword.type = this.checked ? 'text' : 'password';
      });
    }
    //Worth keeping?
    registerForm.addEventListener('submit', function(e) {
      if (registerPassword.value.length < 6) {
        e.preventDefault();
        alert("Password must be at least 6 characters long!");
      }
    });
  }

  //LOGIN

  const loginForm = document.getElementById('loginForm');
  if (loginForm) {
    const loginPassword = document.getElementById('loginPassword');
    const toggleLoginPassword = document.getElementById('toggleLoginPassword');
    if (toggleLoginPassword) {
      toggleLoginPassword.addEventListener('change', function() {
        loginPassword.type = this.checked ? 'text' : 'password';
      });
    }
  }

  // DELETE THE ACC
  const deleteForm = document.getElementById('deleteForm');
  if (deleteForm) {
    deleteForm.addEventListener('submit', function(e) {
      const confirmed = confirm("Are you sure you want to delete your account? This action cannot be undone.");
      if (!confirmed) {
        e.preventDefault();
      }
    });
  }

  // UPDATE THE ACC
  const updateForm = document.getElementById('updateForm');
  if (updateForm) {
    const newPassword = document.getElementById('newPassword');
    const confirmPassword = document.getElementById('confirmPassword');
    updateForm.addEventListener('submit', function(e) {
      if (newPassword.value !== confirmPassword.value) {
        e.preventDefault();
        alert("New password and confirm password do not match!");
      }
    });
  }

  // HOME JS
  const scraperForm = document.getElementById('scraperForm');
  if (scraperForm) {
    //just log that the user is about to scrape
    scraperForm.addEventListener('submit', function() {
      console.log("Scraping posts for the given stock/time_filter...");
    });
  }
});
