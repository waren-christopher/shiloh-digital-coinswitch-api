
from django.shortcuts import render,redirect
from . import coinswitch
import os,time,threading,requests,csv
from dotenv import load_dotenv
from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.conf import settings
from datetime import datetime, timezone, timedelta
from django.template.loader import render_to_string

load_dotenv()

def finish_auto_trade_and_report():
    global calculated_order_id,trade_quantity
    try:
        print("Generating auto trade performance report...")
        # Get recent orders
        resp = coinswitch.recent_orders({})
        api_json_response = resp.json()
        export_file = "coinswitch_trade_history.csv"
        
        # Calculate stats
        stats = analyze_bot_performance(api_json_response,start_order_id=calculated_order_id, export_filename=export_file)
        calculated_order_id = None
        trade_quantity = ""
        print('sdjfjsfjsf',stats)
        
        # Professional HTML Email Template rendered from separate file
        html_message = render_to_string("email_report.html", {"stats": stats})
        
        # Email the report using variables from settings
        email = EmailMessage(
            subject="CoinSwitch Auto Trade Bot Performance [Summary]",
            body=html_message,
            from_email=settings.EMAIL_HOST_USER,
            to=["warenchrist00@gmail.com"]
        )
        email.content_subtype = "html"  # Crucial for HTML rendering
        
        if os.path.exists(export_file):
            email.attach_file(export_file)
            
        email.send(fail_silently=False)
        print("Performance report sent successfully.")
    except Exception as e:
        print(f"Error generating or sending performance report: {str(e)}")

def average_trade_price_api(body):
    try:
        start_date_str = body.get('start_date')
        end_date_str = body.get('end_date')
        ist_tz = timezone(timedelta(hours=5, minutes=30))
        
        start_time = None
        end_time = None
        
        if start_date_str:
            dt = datetime.fromisoformat(start_date_str)
            start_time = dt.replace(tzinfo=ist_tz).timestamp()
            
        if end_date_str:
            dt = datetime.fromisoformat(end_date_str)
            end_time = dt.replace(tzinfo=ist_tz).timestamp()
        else:
            end_time = datetime.now().timestamp()
            
        resp = coinswitch.recent_orders({})
        api_json_response = resp.json()
        export_file = None
        
        stats = analyze_bot_performance(
            api_json_response, 
            start_time=start_time, 
            end_time=end_time, 
            export_filename=export_file
        )

        return JsonResponse({"data": stats, "status": 200})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def analyze_bot_performance(api_json_response, start_order_id=None, start_time=None, end_time=None, export_filename=None):
    orders = []
    response_data = api_json_response.get('data', [])
    if isinstance(response_data, list):
        orders = response_data
    elif isinstance(response_data, dict):
        orders = response_data.get('data', [])
    
    total_trades = 0
    total_usdt_bought = 0.0
    total_inr_spent = 0.0
    cancelled_trades = 0
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    excel_rows = []
    
    for order in orders:
        current_id = order.get('orderId')
        status = order.get('status', '').upper()
        
        try:
            ts_raw = int(order.get('createdAt', 0))
            ts_sec = ts_raw / 1000 if ts_raw > 1e11 else ts_raw
        except (ValueError, TypeError):
            ts_sec = 0
            
        if start_time and ts_sec < start_time:
            continue
        if end_time and ts_sec > end_time:
            continue

        if status == 'CANCELLED':
            cancelled_trades += 1
            
        if status in ['FULFILLED', 'PARTIALLY_CANCELLED']:
            filled_qty = float(order.get('filledQuantity', 0))
            filled_inr = float(order.get('filledQuoteQuantity', 0))
            
            if filled_qty > 0:
                total_trades += 1
                total_usdt_bought += filled_qty
                total_inr_spent += filled_inr
                
            try:
                ts = int(order.get('createdAt', 0))
                ts_sec_dt = ts / 1000 if ts > 1e11 else ts
                dt_ist = datetime.fromtimestamp(ts_sec_dt, tz=timezone.utc).astimezone(ist_tz)
                formatted_time = dt_ist.strftime('%Y-%m-%d %I:%M:%S %p')
            except (ValueError, TypeError):
                formatted_time = "Unknown"

            excel_rows.append({
                "Created At (IST)": formatted_time,
                "Instrument": order.get('instrument', ''),
                "Side": order.get('side', ''),
                "Status": status,
                "Limit Price (INR)": float(order.get('limitPrice', 0)),
                "Requested Qty": float(order.get('quantity', 0)),
                "Filled Qty": filled_qty,
                "Filled Quote (INR)": filled_inr,
                "Cancelled Qty": float(order.get('cancelledQuantity', 0))
            })
            
        # ✅ THE MAGIC STOPPER: 
        # If we just processed the very first order of the session, STOP the loop!
        if start_order_id and current_id == start_order_id:
            print(f"🛑 Reached starting order {start_order_id}. Ignoring older trades.")
            break 
            
    # Calculate VWAP (True Average Price)
    avg_price = total_inr_spent / total_usdt_bought if total_usdt_bought > 0 else 0
    
    # --- 5. CREATE AND SAVE THE EXCEL FILE ---
    if export_filename is not None:
        if excel_rows:
            try:
                if export_filename.endswith('.xlsx'):
                    export_filename = export_filename.replace('.xlsx', '.csv')
                
                keys = excel_rows[0].keys()
                with open(export_filename, 'w', newline='', encoding='utf-8') as output_file:
                    dict_writer = csv.DictWriter(output_file, fieldnames=keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(excel_rows)
                print(f"📊 CSV file saved successfully as: {export_filename}")
            except Exception as e:
                print(f"⚠️ Failed to export file: {e}")
        else:
            # If no matching orders were found, ensure the file is clean or empty
            if os.path.exists(export_filename):
                os.remove(export_filename)
            print("⚠️ No FULFILLED or PARTIALLY_CANCELLED orders found to export.")

    # Return the summary exactly as before
    return {
        "executed_trades": total_trades,
        "cancelled_trades": cancelled_trades,
        "total_usdt": round(total_usdt_bought, 4),
        "total_inr": round(total_inr_spent, 2),
        "average_buy_price": round(avg_price, 4)
    }



def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # 🔥 Replace this with psycopg2 query
        if username == "admin" and password == "1234":
            request.session['user'] = username   # ✅ create session
            return redirect('dashboard')
        else:
            return render(request, "login.html", {"error": "Invalid credentials"})

    return render(request, "login.html")
def auto_trade_page(request):
    return render(request, "auto_trade.html")


bot_running = False
bot_message = ""
current_order_id = None
calculated_order_id = None
trade_quantity = ""
balance = 0
filled_quantity = 0
session=requests.session()

def start_auto_trade(request):
    global bot_running,bot_message,current_order_id

    if request.method == "POST":
        price_range = request.POST.get("price_range")
        min_qty = float(request.POST.get("min_qty"))
        body = {k: v for k, v in request.POST.items() if k not in ('price_range', 'min_qty')}
        print(body)


        if bot_running:
            return JsonResponse({"msg": "Bot already running"})

        bot_running = True
        current_order_id = None
        bot_message = "Starting bot engine..."
        print("▶️ Start auto trade requested. Launching bot thread.")

        thread = threading.Thread(
            target=auto_trade_bot,
            args=(price_range, min_qty, body)
        )
        thread.start()
       # data= auto_trade_bot(price_range,min_qty,body)

        return JsonResponse({"msg":'started' })


def stop_auto_trade(request):
    global bot_running,current_order_id,bot_message
    bot_running = False
    time.sleep(4)
    print("🛑 Stop auto trade requested by user.")
    bot_message = "Stopping bot and cancelling active orders..."
    cancel = None
    if current_order_id:
       cancel=coinswitch.cancel_order({'orderId': current_order_id}).json()
       print(f"Cancel order response: {cancel}")
    else:
       cancel="No active order to cancel"
       print(cancel)
    
    bot_message = "Bot stopped successfully."
    
    # Generate and email performance report
    print("Initiating performance report generation task...")
    threading.Thread(target=finish_auto_trade_and_report).start()
    
    return JsonResponse({"msg": f"bot stopped and {cancel}" })


def auto_trade_status(request):
    global bot_running,bot_message
    return JsonResponse({"running": bot_running,"message": bot_message})


def buy_sell_decision(side,competitor_price,limit_threshold,order_id):
    global bot_message,current_order_id
    if side == 'buy':
        target_price = round(competitor_price + 0.01, 2)
        
        # Safety Check: Did the market push us above our maximum budget?
        if target_price > limit_threshold:
            bot_message = f"Stopped: Target {target_price} exceeded max limit of {limit_threshold}."
            print(f"🛑 {bot_message}")
            if order_id:
                coinswitch.cancel_order({'orderId': order_id})
                current_order_id = None
            return "price range reached"
        return target_price
    else: # sell
        target_price = round(competitor_price - 0.01, 2)
        
        # Safety Check: Did the market drop below our minimum acceptable sell price?
        if target_price < limit_threshold:
            bot_message = f"Stopped: Target {target_price} dropped below min limit of {limit_threshold}."
            print(f"🛑 {bot_message}")
            if order_id:
                coinswitch.cancel_order({'orderId': order_id})
                current_order_id = None
            return "price range reached"
        return target_price
    



def replace_order(cancel_body,body):
    global bot_running, bot_message,current_order_id,trade_quantity,balance,filled_quantity
    try:
        quant=float(body['quantity']) - filled_quantity 
        actual_affordable_quant = quant if quant >= 1000 else balance
        coinswitch.cancel_order({'orderId': current_order_id}).json()
        if 1000 > quant and balance > float(trade_quantity):
          print('getting total quantity from trade_quntity ',trade_quantity)
          return trade_quantity
        elif actual_affordable_quant < 300:
            print(f"🛑 [STOP] Remaining amount ({actual_affordable_quant}) or balance is below the 300 INR minimum. Stopping safely.")
            bot_running = False
            bot_message = "Completed: Target quantity met or insufficient funds remaining."
            return ""

        print(f"Calculated new quantity to place: {actual_affordable_quant}")   
        # 4. If we made it here, the math is 100% safe to send to the API!
        return str(round(actual_affordable_quant, 2))
    except requests.exceptions.ConnectionError as e:
            print(f"📡 [NETWORK] Connection dropped in replace_order. Will retry. Error: {str(e)}")
            time.sleep(5)
            return ""
    except Exception as e:
        print(f"💥 CRASH IN REPLACE BLOCK: {str(e)}")
        bot_running=False
        bot_message = f"error : {str(e)}"
        print(f"error : {str(e)}")
        return ""

def check_balance(body):
    global trade_quantity,bot_running,bot_message
    time.sleep(2)
    res = coinswitch.broker_balance(body).json()
    balance=float(res['data']['Available']['inr'])
    print(f'body quanti is {body['quantity']}')
    quan= body['quantity'] if balance > float(body['quantity']) else balance
   # trade_quantity = str(round(float(quan),2))
    print('balance is ',balance,'and quantity is',quan,'adn trade quantiy is',trade_quantity)
    if 500 > float(quan):
        bot_running = False
        bot_message ="Auto Trade completed"
        time.sleep(5)
        return ""
    return quan

def auto_trade_bot(price_range, min_qty, body):
    global bot_running, bot_message,current_order_id,trade_quantity,balance,filled_quantity,calculated_order_id
    order_print  = "initial"
    current_placed_price = None
    side = body['side'].lower()  # 'buy' or 'sell'
    limit_threshold = float(price_range) # Max price to buy, or Min price to sell

    bot_message = f"Bot started. Searching for ideal {side.upper()} entry..."
    print(f"🚀 Bot initialized: Side={side.upper()}, Limit Threshold={limit_threshold}, Min Qty={min_qty}")

    while bot_running:
        loop_start_time = datetime.now()
        try:
            # We skip printing orderbook fetch every 3 seconds to avoid terminal spam, but we track status.
            res = session.get("https://exchange.coinswitch.co/api/v2/public/depth/?instrument=usdt/inr")
            
            if res.status_code != 200:
                bot_message=f"Error fetching orderbook: {res.json()}"
                return
                
            data = res.json()
            levels = data["data"][side]

            # 1. Find the top COMPETITOR price (ignoring our own order)
            competitor_price = None
            for level in levels:
                price = float(level[0])
                qty = float(level[1])

                # CRITICAL: Do not compete with our own active order
                if current_placed_price is not None and price == current_placed_price:
                    continue

                # Ensure competitor has enough volume to matter
                if qty >= min_qty:
                    competitor_price = price
                    break 

            if competitor_price is None:
                bot_message = "Scanning: No competitor found meeting min quantity criteria."
                print("No valid competitor levels found. Waiting...")
                loop_end_time = datetime.now()
                elapsed_seconds = (loop_end_time - loop_start_time).total_seconds()
                print(f"🏁 Loop completed in {elapsed_seconds:.3f} seconds")
                if elapsed_seconds < 1:
                    time.sleep(1)
                continue

            target_price=buy_sell_decision(side,competitor_price,limit_threshold,current_order_id)
            if target_price == "price range reached":
                time.sleep(5)
                continue
            # 2. Determine our target price (+0.01 for buy, -0.01 for sell)

            print(f"Competitor: {competitor_price} | Our Target: {target_price} | Currently Placed at: {current_placed_price}")

            # 3. State Machine: Place, Hold, or Cancel/Replace
            if current_order_id is None:
                # PLACE NEW ORDER
                body['limitPrice'] = str(target_price)
                trade_quantity = body['quantity']
                print(f'body quantity is {body['quantity']} and trade quantity is {trade_quantity}')
                bot_message = f"Placing {order_print} {side} order at ₹{target_price}..."
                print(f"⏳ Placing {order_print} {side} order at ₹{target_price} for {trade_quantity}...")
                
                response = coinswitch.buy_limit_order(body) if side == 'buy' else coinswitch.sell_limit_order(body)
                resp_data = response.json()
                
                # Check for success (Adjust the condition based on CoinSwitch API's exact success response)
                if balance == 0:
                    def fetch_balance(body):
                        global balance
                        res = coinswitch.broker_balance(body).json()
                        balance=float(res['data']['Available']['inr'])
                        print('balance is ',balance)
                    threading.Thread(target=fetch_balance, args=(body,)).start()
                    print('thread started,,,,')
                if response.status_code == 200:
                    current_order_id = resp_data['data']['orderId']    
                    current_placed_price = target_price
                    if not calculated_order_id:
                        calculated_order_id = current_order_id
                    bot_message = f"✅ Active {side.upper()} order at ₹{target_price}"
                    print(f"✅ Order Placed Successfully. ID: {current_order_id} at ₹{target_price}")
                    loop_end_time = datetime.now()
                    elapsed_seconds = (loop_end_time - loop_start_time).total_seconds()
                    print(f"🏁 Loop completed in {elapsed_seconds:.3f} seconds")
                    if elapsed_seconds < 1:
                        time.sleep(1)
                    continue
                else:
                    bot_message = f"Failed to place order: {resp_data.get('message', 'API Error')}"
                    print(f"❌ Failed to place order: {resp_data}")
                    bot_running = False
                    return
            else:
 
                    try:
                        order_det=coinswitch.particular_order_details(current_order_id).json()
                        filled_quantity=float(order_det['data']['filledQuoteQuantity'])
                        if order_det['data']['status'] == 'FULFILLED': # or 100 > float(body['quantity']) - float(order_det['data']['filledQuoteQuantity']):
                            if 500 > balance:
                                res = coinswitch.broker_balance(body).json()
                                balance=float(res['data']['Available']['inr'])
                                if 500 > balance:
                                   bot_running = False
                                   bot_message = "Auto Trade successfully completed" 
                                   return
                                current_order_id = None
                                body['quantity']=trade_quantity
                                continue
                            raw_quantity= float(float(trade_quantity) if balance > float(trade_quantity) else str(balance))
                            body['quantity'] = str(round(raw_quantity, 2))
                            latest_order_id = coinswitch.buy_limit_order(body).json() if side == 'buy' else coinswitch.sell_limit_order(body).json()
                        
                            try:
                                current_order_id = latest_order_id['data']['orderId'] 
                                print('order fullfilled so placed a new order')
                            except Exception as e:
                               print("error while placing the new order","order details",latest_order_id,"current order id",current_order_id)
                               print('checking balance........')
                               body['quantity']= check_balance(body)
                               print('calculated final amount',body['quantity'])
                               if not body['quantity']:
                                   break
                               current_order_id = None
                               continue
                            current_placed_price = body['limitPrice']
                            bot_message = "order fullfilled so placed a new order..."
                            loop_end_time = datetime.now()
                            elapsed_seconds = (loop_end_time - loop_start_time).total_seconds()
                            print(f"🏁 Loop completed in {elapsed_seconds:.3f} seconds")
                            if elapsed_seconds < 1:
                                time.sleep(1)
                            continue
                    except Exception as e:
                        print('erorroro',str(e))
                        bot_message = f"ererr {str(e)}"
                        bot_running = False
                        return
                

                # CHECK IF WE ARE STILL AT THE TOP
            if current_placed_price != target_price:
                bot_message = f"Market moved. Re-adjusting order to ₹{target_price}..."
                print(f"📉 Market moved! We are at {current_placed_price}, new target is {target_price}. Replacing order...")
                try:
                    cancel_body = {'orderId': current_order_id}
                    quant = replace_order(cancel_body,body)
                    if quant:
                        body['quantity'] = quant
                    else:
                        print("No quantity left or min threshold not met. Exiting replacement flow.")
                        break
                    target_price=buy_sell_decision(body['side'].lower(),competitor_price,limit_threshold,current_order_id)
                    if target_price == "price range reached":
                        print("Price range reached during replacement. Pausing...")
                        bot_message = "Price range reached during replacement. Pausing..."
                        time.sleep(3)
                        continue
                    body['limitPrice'] = str(target_price)
                    print(f"Sending API request to place new order at {target_price}...")
                    bot_message = f"Placing replacement order at ₹{target_price}..."
                    latest_order_id = coinswitch.buy_limit_order(body).json() if side == 'buy' else coinswitch.sell_limit_order(body).json()
                    # print('order info',latest_order_id)
                    try:
                      current_order_id = latest_order_id['data']['orderId'] 
                    except Exception as e:
                        print("error while placing the new order will retry again",current_order_id,"current order id",latest_order_id)
                        print('checking balance........')
                        body['quantity']= check_balance(body)
                        print('after check balance',body['quantity'])
                        if not body['quantity']:
                            break
                        current_order_id = None
                        continue
                    current_placed_price = target_price
                    bot_message = f"✅ Position re-adjusted to ₹{target_price}"
                    print(f"✅ Replaced order successfully. New ID: {current_order_id}")
                except Exception as e:
                    print(f"💥 CRASH AT BOTTOM OF REPLACE: {str(e)}")
                    bot_message =f"System error during replace step: {str(e)}"
                    bot_running = False
                    return
            else:
                print(f"✅ We are at the top of the book. Holding position at {current_placed_price}")
                bot_message = f"✅ Best position maintained at ₹{current_placed_price}. Awaiting fill."

        except requests.exceptions.ConnectionError as e:
            print(f"📡 [NETWORK] Connection dropped. Will retry. Error: {str(e)}")
            bot_message = "Network connection dropped. Automatically retrying..."
            time.sleep(5)

        except Exception as e:
            print(f"⚠️ An unexpected error occurred in loop: {e}")
            bot_message = f"Temporarily disrupted: {str(e)}"
            time.sleep(5)
            
        # print('sleeping')
        loop_end_time = datetime.now()
        elapsed_seconds = (loop_end_time - loop_start_time).total_seconds()
        print(f"🏁 Loop completed in {elapsed_seconds:.3f} seconds")
        if elapsed_seconds < 1.15:
            time.sleep(1)

#enddddddddddddddddddddddd

def dashboard(request):
    # if not request.session.get('user'):
    #     return redirect('login')
        
    if request.method == "GET":
        return render(request, "dashboard.html")

    if request.method == "POST":
        api_action = request.POST.get('api')
        
        # Clean standard django/frontend keys from the payload
        body = {k: v for k, v in request.POST.items() if k not in ('api', 'csrfmiddlewaretoken')}
        
        try:
            if api_action == 'average_trade_price':
                return average_trade_price_api(body)
                
            # Dynamically call the matching function in coinswitch.py
            api_function = getattr(coinswitch, api_action)
            
            # Execute the function with the cleaned body payload
            response = api_function(body)
            try:
                data = response.json()
            except Exception:
                data = response.text
            return JsonResponse({"data": data, "status": response.status_code})

        except AttributeError:
            return JsonResponse({"error": f"API endpoint '{api_action}' not configured."}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)