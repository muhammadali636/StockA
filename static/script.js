//DOM
document.addEventListener('DOMContentLoaded', function() {
  console.log("Global JS loaded!");

  //REG PAGE:

  const registerForm = document.getElementById('registerForm');
  if (registerForm) {
    const registerPassword = document.getElementById('registerPassword');
    const toggleRegPassword = document.getElementById('toggleRegPassword');

    const registerUsername = document.getElementById('registerUsername');

    //pass show/hide
    if (toggleRegPassword) {
      toggleRegPassword.addEventListener('change', function() {
        if (this.checked) {
          registerPassword.type = 'text';
        } 
        else {
          registerPassword.type = 'password';
        }
      });
    }

    registerForm.addEventListener('submit', function(e) {
      if (registerUsername.value.length < 6) {
        e.preventDefault();
        alert("Username must be atleast 6 characters long!");
      }
    });
    
    registerForm.addEventListener('submit', function(e) {
      if (registerPassword.value.length < 6) {
        e.preventDefault();
        alert("Password must be atleast 6 characters long!");
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
        if (this.checked) {
          loginPassword.type = 'text';
        } 
        else {
          loginPassword.type = 'password';
        }
      });
    }
  }

  //DEL THE ACCOUNT
  const deleteForm = document.getElementById('deleteForm');
  if (deleteForm) {
    deleteForm.addEventListener('submit', function(e) {
      const confirmed = confirm("Are you sure you want to delete your account? This action cannot be undone.");
      if (!confirmed) {
        e.preventDefault();
      }
    });
  }

  //UPDATE THE ACCOUNT
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
    scraperForm.addEventListener('submit', function() {
      console.log("Scraping posts for the given stock/time_filter..."); 
    });

    //DONE toggle the display of <hr> elements
    function toggleSearchDividers() {
      const searchedSections = document.querySelectorAll('[data-searched="true"]');      //checks for  sec with data-searched="true"
      let shouldShowDividers = false;      //init  a flag to see if any sec exists
      if (searchedSections.length > 0) {
        shouldShowDividers = true;
      }

      const searchDividers = document.querySelectorAll('.search-divider'); //getall hr lines

      //show or hide <hr> elements based on the flag
      searchDividers.forEach(function(divider) {
        if (shouldShowDividers) {
          divider.style.display = 'block';
        } else {
          divider.style.display = 'none';
        }
      });
    }
    toggleSearchDividers();    //call once the DOM is fully loaded

    //SELECTALL / DESELECT ALL FUNCTIONS
    const selectAllBtn = document.getElementById('selectAllBtn'); //select all button
    const deselectAllBtn = document.getElementById('deselectAllBtn'); //deselectall button

    if (selectAllBtn && deselectAllBtn) {
      selectAllBtn.addEventListener('click', function() {
        const checkboxes = document.querySelectorAll('input[name="subreddits"]');
        checkboxes.forEach(function(checkbox) {
          checkbox.checked = true;
        });
      });

      deselectAllBtn.addEventListener('click', function() {
        const checkboxes = document.querySelectorAll('input[name="subreddits"]');
        checkboxes.forEach(function(checkbox) {
          checkbox.checked = false;
        });
      });
    }
  }
});