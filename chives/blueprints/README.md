# Available views
The following routes should be implemented:

* `/auth`  
blueprint for handling user management and authentication
  * `/auth/register`  
  Allows a user to sign up using a username/password combination  
  __QA__:  
    * remove the development database, then go onto the registration 
  page and sign-up with proper username/password combination, and check that 
  the user is redirected to the login page. 
    * Return to the registration page,  and sign-up against using the same 
    username, this time checking that an error message shows up regarding 
    duplicate username. 
    * Reload the registration page, sign-up using mismatched passwords, then 
    check that there is a error message regarding mismatched passwords
  * `/auth/login`  
  Allows user to log in  
  __QA__:  
    * Remove the development database, then from the `/auth/register` route, 
    create a new user
    * Login with the new user, confirm that the `/debug/is_authenticated` route 
    displays a correct "you are connected as `username`" 
    * Use the `/auth/logout` route to logout, then go to 
    `/debug/is_authenticated`, this time checking a redirect to the login page.
  * `/auth/logout`  
  Allows the user to log out
* `/exchange`  
  this route redirects to `/exchange/dashboard`
  * `/exchange/dashboard` (login required)  
  For displaying a summary of the user's portfolio: what stocks does this user 
  hold, how much cash does it have
  * `/exchange/start_company` (login required)
  Create a company by filling out an IPO form
  * `/exchange/market/<security_symbol: str>` (login required)    
  For the given symbol, display the current market price (price of the latest 
  transaction), a graph of traded prices that can have day/week/month/year 
  zooms (similar to the summary card displayed when searching for stocks on 
  Google)
  * `/exchange/submit_order` (login required)    
  Submit new order through a form
  * `/exchange/view_orders` (login required)  
  View the status of submitted orders
  * `/exchange/view_transactions` (login required)   
  View transactions