from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.db import connection
from django.views.decorators.csrf import csrf_exempt
from werkzeug.security import generate_password_hash, check_password_hash
import os

from .scraper import scrape_posts, is_valid_ticker
from .priceplot import generate_post_counts_stock_plot
from .volumeplot import generate_post_counts_volume_plot

#TODO FIX: NotOpenSSLWarning - urllib3 v2 only supports OpenSSL 1.1.1+, currently the 'ssl' module is compiled with 'LibreSSL 2.8.3'. See: https://github.com/urllib3/urllib3/issues/3020 wtf
#postgre only configured for local.

#CONNECTION TO DATABASE: psql -h localhost -d scraper -U muhammadali636

#time filter mapping
TIME_FILTER_MAPPING = {
    'day': '1d',
    'week': '5d',
    'month': '1mo',
    'year': '1y',
    'all': 'max'
}

#REG
def register_view(request):
    if request.method == 'POST':
        #set the username and password from the form.
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        with connection.cursor() as cur:
            #cheecks if user already exists
            cur.execute("SELECT 1 FROM users WHERE username = %s", [username])
            user_exists = cur.fetchone()
            if user_exists:
                messages.error(request, "Username already exists. Please try again.")
            else:
                #werkzeug password hash for user registration (security reasons) CHECK HASH.
                hashed_password = generate_password_hash(password, method='pbkdf2:sha256') # Insert new user. do not remove hash method or --> warning.
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", [username, hashed_password])
                messages.success(request, "Registration successful!")
                #REDIRECT TO LOGIN
                return redirect(reverse('login'))
    return render(request, 'register.html')


#LOGIN
def login_view(request):
    if request.method == 'POST':
        #set username and password from post.
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        with connection.cursor() as cur:
            #find user by username in db.
            cur.execute("SELECT username, password FROM users WHERE username = %s", [username])
            result = cur.fetchone()
            if not result:
                messages.error(request, "User does not exist.")
                #stay on login
                return redirect(reverse('login'))
            db_username, db_hashed_password = result
            if check_password_hash(db_hashed_password, password):
                #store username in session
                request.session['username'] = db_username
                messages.success(request, "Logged in successfully!")
                #REDIRECT TO HOME
                return redirect(reverse('home'))
            else:
                #Wrong password
                messages.error(request, "Wrong password.")
    return render(request, 'login.html')


#DELETE ACCOUNT
def delete_view(request):
    #REDIRECT TO LOGIN
    if 'username' not in request.session:
        messages.error(request, "You must be logged in to delete your account!")
        return redirect(reverse('login'))

    if request.method == 'POST':
        #find user via username on db.
        username_form = request.POST.get('username', '').strip()
        password_form = request.POST.get('password', '').strip()
        current_session_user = request.session['username']
        if username_form != current_session_user:
            flash_msg = "The username does not match the logged-in account."
            messages.error(request, flash_msg)
            return render(request, 'delete.html')

        with connection.cursor() as cur:
            #check if user (from session) actually exists
            cur.execute("SELECT password FROM users WHERE username = %s", [current_session_user])
            result = cur.fetchone()

            if not result:
                messages.error(request, "User does not exist.")
                #stay on login
                return redirect(reverse('login'))

            db_hashed_password = result[0]
            if check_password_hash(db_hashed_password, password_form):
                #delete user from database.
                cur.execute("DELETE FROM users WHERE username = %s", [current_session_user])
                request.session.pop('username', None)
                messages.success(request, "Account deleted successfully, sorry to see you go :(")
                #REDIRECT TO LOGIN
                return redirect(reverse('login'))
            else:
                messages.error(request, "Invalid username or password.")

    return render(request, 'delete.html')


#UPDATE PASSWORD
def update_view(request):
    #REDIRECT TO LOGIN
    if 'username' not in request.session:
        messages.error(request, "You must be logged in to update your password.")
        return redirect(reverse('login'))

    if request.method == 'POST':
        old_password = request.POST.get('old_password', '').strip()
        new_password = request.POST.get('new_password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        username = request.session['username']

        with connection.cursor() as cur:
            #heck if user exists ELSE redirect
            cur.execute("SELECT password FROM users WHERE username = %s", [username])
            result = cur.fetchone()

            if not result:
                messages.error(request, "User does not exist.")
                return redirect(reverse('update'))

            db_hashed_password = result[0]

            # Check if the old password is correct
            if check_password_hash(db_hashed_password, old_password):
                # Update the password if confirmation matches
                if new_password == confirm_password:
                    hashed_new_password = generate_password_hash(new_password, method='pbkdf2:sha256')
                    cur.execute("UPDATE users SET password = %s WHERE username = %s", [hashed_new_password, username])
                    messages.success(request, "Password updated!")
                    #return to home page on success
                    return redirect(reverse('home'))
                else:
                    messages.error(request, "New passwords do not match.")
            else:
                messages.error(request, "Wrong old password.")

    return render(request, 'update.html')


#SIGNOUT AND CLEAR SESSION
def signout_view(request):
    #pop username from sesh to logout.
    request.session.pop('username', None)
    messages.success(request, "You have been logged out.")
    #redirect to login after signout
    return redirect(reverse('login'))


#home
def home_view(request):
    #REDIRECT TO LOGIN
    if 'username' not in request.session:
        messages.error(request, "You must be logged in to access this page.")
        return redirect(reverse('login'))
    
    stock = None
    posts_data = []
    metrics = {}
    overall_sentiment_label = None
    plot_prices = None
    plot_volume = None
    total_posts = 0
    timeframe_description = ""

    if request.method == 'POST':
        #set stock from the form
        stock = request.POST.get('stock', '').strip().upper()
        time_filter = request.POST.get('time_filter', '').strip().lower()
        selected_subreddits = request.POST.getlist('subreddits') 

        if not selected_subreddits:
            # Please select at least one subreddit.
            messages.warning(request, "Please select at least one subreddit.")
        elif not stock:
            # Please enter a stock symbol
            messages.warning(request, "Please enter a stock symbol.")
        else:
            # MUST CHECK if ticker is valid FIRST IF NOT flash else flash
            if not is_valid_ticker(stock):
                # Ticker not found
                messages.warning(request, "Ticker not found.")
            else:
                period = TIME_FILTER_MAPPING.get(time_filter, '1mo')

                #1) SCRAPE (user-chosen timeframe) for the main results
                try:
                    posts_data, metrics, overall_sentiment_label = scrape_posts(
                        stock, time_filter, selected_subreddits, period
                    )
                except Exception as e:
                    messages.error(request, f"ERROR while scraping posts: {e}")
                    posts_data, metrics, overall_sentiment_label = [], {}, None

                if not posts_data and not metrics:
                    messages.warning(request, "No valid posts found or invalid inputs.")
                else:
                    total_posts = len(posts_data)

                #textual label for the timeframe
                if period == '1mo':
                    timeframe_description = "1 Month"
                elif period == '1d':
                    timeframe_description = "1 Day"
                elif period == '5d':
                    timeframe_description = "5 Days"
                elif period == '1y':
                    timeframe_description = "1 Year"
                else:
                    timeframe_description = "All Time"

                # ALWAYS GET 1 YEAR WORTH OF POSTS FOR PLOTS ignores the user inputted time_filter
                try:
                    plot_posts_data, _, _ = scrape_posts(stock, time_filter='year', subreddits=selected_subreddits, period='1y')
                except Exception as e:
                    messages.error(request, f"ERROR while scraping data for the 12-month plot: {e}")
                    plot_posts_data = []

                #gen plots
                if plot_posts_data:
                    try:
                        plot_prices = generate_post_counts_stock_plot(plot_posts_data, stock) 
                    except Exception as e:
                        messages.error(request, f"ERROR generating the stock plot: {e}")
                        plot_prices = None

                    try:
                        plot_volume = generate_post_counts_volume_plot(plot_posts_data, stock)
                    except Exception as e:
                        messages.error(request, f"ERROR generating the volume plot: {e}")
                        plot_volume = None

    return render(request, 'home.html', {
        'stock': stock,
        'posts_data': posts_data,
        'metrics': metrics,
        'overall_label': overall_sentiment_label,
        'plot_prices': plot_prices,
        'plot_volume': plot_volume,
        'total_posts': total_posts,
        'timeframe_description': timeframe_description if timeframe_description else "",
    })
