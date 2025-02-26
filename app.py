#!/usr/bin/env python
# coding: utf-8
from io import BytesIO
import requests
from datetime import datetime
import jwt
import pandas as pd
import matplotlib.pyplot as plt
import os
import time
import threading
from flask import Flask, send_file, render_template_string, Response

# Initialize Flask app
app = Flask(__name__)

# API Credentials
api_key = "8b0c7d16-b3f4-424f-a95d-39e209398f55"
secret_key = "FjQGeH5KkzL20xw7ahTsDyWFp6LTPeP6Ify93wkjaKw"

# List of branch codes
branch_codes = [
    "108591", "108592", "110612", "108607", "108610", "108612", "108613", "109023", "108650",
    "108649", "108783", "108635", "108636", "108589", "108593", "108782", "108631", "108634",
    "108615", "108614", "108632", "108633", "108668", "108667", "108666", "108669", "108670",
    "108665", "108638", "108646", "108643", "108642", "108644", "108648", "108641", "108640", "110918",
    "108672", "108673", "108675", "108677", "108651", "109967", "108661", "108653", "108658", "110955", "111017", "111072",
    "108692", "108652", "108656", "108659", "110611", "110738", "110771", "110770", "110785", "110851", "110853", "108816" ,"110935"
]

# Paths for each chart
STATIC_DIR = "static"
TABLE_CHART = "table_chart.png"
NET_AMOUNT_CHART = "net_amount_chart.png"
BILL_CUTS_CHART = "bill_cuts_chart.png"
NET_AMOUNT_BY_BRANCH_TYPE_CHART = "net_amount_by_branch_type_chart.png"
BILL_CUTS_BY_BRANCH_TYPE_CHART = "bill_cuts_by_branch_type_chart.png"

# Full paths
table_chart_path = os.path.join(STATIC_DIR, TABLE_CHART)
net_amount_chart_path = os.path.join(STATIC_DIR, NET_AMOUNT_CHART)
bill_cuts_chart_path = os.path.join(STATIC_DIR, BILL_CUTS_CHART)
net_amount_by_branch_type_chart_path = os.path.join(STATIC_DIR, NET_AMOUNT_BY_BRANCH_TYPE_CHART)
bill_cuts_by_branch_type_chart_path = os.path.join(STATIC_DIR, BILL_CUTS_BY_BRANCH_TYPE_CHART)

# In-memory chart storage as backup in case file system permissions are restricted
chart_memory_store = {
    "table": None,
    "net_amount": None,
    "bill_cuts": None,
    "net_amount_by_branch_type": None,
    "bill_cuts_by_branch_type": None
}

# Ensure the static folder exists
def ensure_static_dir():
    try:
        os.makedirs(STATIC_DIR, exist_ok=True)
        print(f"Static directory created/confirmed at: {os.path.abspath(STATIC_DIR)}")
        # Test write permissions
        test_file = os.path.join(STATIC_DIR, "test_write.txt")
        with open(test_file, 'w') as f:
            f.write("Test write access")
        os.remove(test_file)
        print("Write access to static directory confirmed.")
        return True
    except Exception as e:
        print(f"⚠️ Error with static directory: {e}")
        print(f"Will use in-memory storage for charts as fallback.")
        return False

# Dictionary for mapping branch codes to branch types
branch_type_mapping = {
    "110738": "Signature", "110770": "Signature", "110771": "Signature", "110785": "Signature",
    "110955": "Signature", "108650": "Signature", "111017": "Signature", "110851": "Signature",
    "108633": "Partial Signature", "108634": "Partial Signature", "108607": "Partial Signature",
    "108610": "Partial Signature", "108613": "Partial Signature", "108638": "Partial Signature",
    "110611": "Partial Signature", "108593": "Express", "108635": "Express", "108636": "Express",
    "108644": "Express", "108646": "Express", "108782": "Express", "110918": "Kiosk", "111072": "Kiosk"
}

# Function to map branch codes to branch types
def map_branch_type(branch_code):
    return branch_type_mapping.get(str(branch_code), "Other")  # Default to "Other" if not in the list

# Create initial empty charts
def create_initial_charts():
    has_file_storage = ensure_static_dir()
    
    # Create a placeholder loading image
    plt.figure(figsize=(14, 8))
    plt.text(0.5, 0.5, "Loading data...", horizontalalignment='center', 
             verticalalignment='center', fontsize=24)
    plt.axis('off')
    
    # Save both to file system (if available) and in-memory
    for chart_name in ["table", "net_amount", "bill_cuts", "net_amount_by_branch_type", "bill_cuts_by_branch_type"]:
        # Save to memory buffer
        buffer = BytesIO()
        plt.savefig(buffer, format="png")
        buffer.seek(0)
        chart_memory_store[chart_name] = buffer.getvalue()
        
        # Try to save to file system
        if has_file_storage:
            try:
                chart_path = os.path.join(STATIC_DIR, f"{chart_name}_chart.png")
                plt.savefig(chart_path)
                print(f"Created placeholder chart at {chart_path}")
            except Exception as e:
                print(f"Could not save placeholder to disk for {chart_name}: {e}")
    
    plt.close()

def fetch_sales_data():
    all_items = []
    date_str = datetime.today().strftime('%Y-%m-%d')
    print(f"📅 Fetching sales data for {date_str}...")

    for branch_code in branch_codes:
        last_key = None
        print(f"Fetching data for branch {branch_code}...")

        while True:
            payload = {
                "iss": api_key,
                "iat": datetime.utcnow(),
                "jti": "YOUR_UNIQUE_JWT_ID"
            }

            token = jwt.encode(payload, secret_key, algorithm="HS256")

            headers = {
                "x-api-key": api_key,
                "x-api-token": token
            }

            url = f"https://api.ristaapps.com/v1/sales/summary?branch={branch_code}&day={date_str}"
            if last_key:
                url += f"&lastKey={last_key}"

            try:
                response = requests.get(url, headers=headers, timeout=10)
                response.raise_for_status()
                data = response.json().get('data', [])

                if data:
                    print(f"Data received for branch {branch_code} ({len(data)} records).")
                    flattened_data = pd.json_normalize(data)
                    all_items.append(flattened_data)
                else:
                    print(f" No data received for branch {branch_code}.")

                last_key = response.json().get("lastKey")
                if not last_key:
                    break
            except Exception as e:
                print(f"Error fetching data for branch {branch_code}: {e}")
                break  # Move to next branch on error

    if all_items:
        sales_df = pd.concat(all_items, ignore_index=True)
        closed_sales_df = sales_df[sales_df['status'] == 'Closed']

        if closed_sales_df.empty:
            print(" No closed sales records found.")

        aggregated_sales = closed_sales_df.groupby(['branchName', 'branchCode']).agg({
            'netAmount': 'sum',
            'invoiceNumber': 'nunique'
        }).reset_index()

        aggregated_sales.rename(columns={'netAmount': 'Net Amount', 'invoiceNumber': 'Bill Cuts'}, inplace=True)

        print("Sales data successfully processed.")
        return aggregated_sales

    print("No sales data available.")
    return pd.DataFrame()  # Return empty DataFrame if no data


def update_all_charts():
    """Single function to update all charts in sequence"""
    while True:
        try:
            print(f"🔄 Starting chart update cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            aggregated_sales = fetch_sales_data()
            
            if aggregated_sales.empty:
                print("⚠️ No data fetched from API. Skipping chart updates.")
                time.sleep(60)  # Wait a minute before retrying
                continue

            print(f"✅ Data fetched at {datetime.now()}, updating charts...")

            chart_types = [
                ("table", table_chart_path, plot_table_chart),
                ("net_amount", net_amount_chart_path, plot_net_amount_chart), 
                ("bill_cuts", bill_cuts_chart_path, plot_bill_cuts_chart),
                ("net_amount_by_branch_type", net_amount_by_branch_type_chart_path, plot_net_amount_by_branch_type_chart),
                ("bill_cuts_by_branch_type", bill_cuts_by_branch_type_chart_path, plot_bill_cuts_by_branch_type_chart)
            ]
            
            for chart_name, chart_path, plot_function in chart_types:
                update_single_chart(aggregated_sales, chart_name, chart_path, plot_function)
                print(f"📊 {chart_name} chart updated.")
                plt.close('all')

            print("✅ All charts updated successfully.")
            
        except Exception as e:
            print(f"❌ Error in chart update cycle: {e}")
            import traceback
            traceback.print_exc()

        print("⏳ Sleeping for 5 minutes until next update...")
        time.sleep(300)  # 5-minute refresh


from io import BytesIO

def update_single_chart(data, chart_name, chart_path, plot_function):
    """Update a single chart with proper error handling and file management"""
    print(f"Generating {chart_name} chart...")
    
    has_file_storage = ensure_static_dir()
    
    try:
        # Create a figure for this chart
        plt.figure(figsize=(16, 8), num=f"{chart_name}_{time.time()}")
        
        # Generate the chart
        buffer = BytesIO()
        plot_function(data, buffer)
        buffer.seek(0)
        
        # Store in memory
        chart_memory_store[chart_name] = buffer.getvalue()
        print(f"Successfully updated {chart_name} chart in memory")
        
        # Try to save to disk if we have file storage
        if has_file_storage:
            try:
                # Generate a new buffer for file storage
                file_buffer = BytesIO()
                plot_function(data, file_buffer)
                file_buffer.seek(0)
                
                # Ensure the directory exists
                os.makedirs(os.path.dirname(chart_path), exist_ok=True)
                
                # Save to disk
                with open(chart_path, 'wb') as f:
                    f.write(file_buffer.getvalue())
                print(f"Successfully updated {chart_name} chart on disk")
            except Exception as e:
                print(f"Error saving {chart_name} chart to disk: {e}")
    except Exception as e:
        print(f"Error generating {chart_name} chart: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Close the plot
        plt.close()

# Function to generate table chart
def plot_table_chart(aggregated_sales, save_path):
    try:
        fig, ax = plt.subplots(figsize=(14, 8), num=f"table_chart_{time.time()}")
        ax.axis("off")

        # Calculate Overall Oyalo Sales
        overall_sales = aggregated_sales[['Net Amount', 'Bill Cuts']].sum()

        # Display "Overall Oyalo Sales"
        ax.text(
            0.5, 1.0,  
            f"OYALO SALES TODAY\nNet Amount: ₹{overall_sales['Net Amount']:,.2f} | Bill Cuts: {overall_sales['Bill Cuts']}",
            fontsize=24, fontweight="bold", ha="center",
            transform=ax.transAxes, bbox=dict(facecolor='yellow', alpha=0.5)
        )

        # Add timestamp
        ax.text(
            0.5, 0.95,
            f"Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            fontsize=12, ha="center", transform=ax.transAxes
        )

        # Prepare table data
        table_data = []
        for _, row in aggregated_sales.iterrows():
            table_data.append([
                row['branchName'],
                f"₹{row['Net Amount']:,.2f}",  
                f"{row['Bill Cuts']}"  
            ])

        # Render branch-wise sales
        table = ax.table(cellText=table_data, 
                        colLabels=["Branch", "Net Amount (₹)", "Bill Cuts"],  
                        loc="upper center", cellLoc="center", bbox=[0, 0.2, 1, 0.75])

        table.auto_set_font_size(False)
        table.set_fontsize(14)
        table.scale(1.5, 1.5)

        # Save the chart to the provided buffer or path
        if isinstance(save_path, (str, os.PathLike)):
            plt.savefig(save_path, bbox_inches="tight", dpi=100)
        else:
            plt.savefig(save_path, format="png", bbox_inches="tight", dpi=100)
        return True
    except Exception as e:
        print(f"Error in plot_table_chart: {e}")
        return False
    finally:
        plt.close()

# Function to generate net amount bar chart
def plot_net_amount_chart(aggregated_sales, save_path):
    try:
        plt.figure(figsize=(16, 8), num=f"net_amount_chart_{time.time()}")
        
        aggregated_sales = aggregated_sales.sort_values(by="Net Amount", ascending=False)
        bars = plt.bar(aggregated_sales["branchName"], aggregated_sales["Net Amount"], color="blue")

        # Adding labels above each bar (HORIZONTAL TEXT)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5, 
                    f"₹{int(yval):,}", ha="center", fontsize=12, fontweight="bold", color="black", rotation=90)

        plt.xlabel("Branch")
        plt.ylabel("Net Amount (₹)")
        plt.title(f"Net Amount by Branch (Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        
        # Save the chart to the provided buffer or path
        if isinstance(save_path, (str, os.PathLike)):
            plt.savefig(save_path, dpi=100)
        else:
            plt.savefig(save_path, format="png", dpi=100)
        return True
    except Exception as e:
        print(f"Error in plot_net_amount_chart: {e}")
        return False
    finally:
        plt.close()

# Function to generate bill cuts bar chart
def plot_bill_cuts_chart(aggregated_sales, save_path):
    try:
        plt.figure(figsize=(16, 8), num=f"bill_cuts_chart_{time.time()}")
        
        aggregated_sales = aggregated_sales.sort_values(by="Bill Cuts", ascending=False)
        bars = plt.bar(aggregated_sales["branchName"], aggregated_sales["Bill Cuts"], color="green")

        # Adding labels above each bar (VERTICAL TEXT)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5,  # Position above bar
                    f"{int(yval)}", ha="center", fontsize=12, fontweight="bold", 
                    color="black", rotation=90)  # ROTATE TEXT 90° VERTICALLY

        plt.xlabel("Branch")
        plt.ylabel("Bill Cuts")
        plt.title(f"Bill Cuts by Branch (Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        
        # Save the chart to the provided buffer or path
        if isinstance(save_path, (str, os.PathLike)):
            plt.savefig(save_path, dpi=100)
        else:
            plt.savefig(save_path, format="png", dpi=100)
        return True
    except Exception as e:
        print(f"Error in plot_bill_cuts_chart: {e}")
        return False
    finally:
        plt.close()

def plot_net_amount_by_branch_type_chart(aggregated_sales, save_path):
    try:
        plt.figure(figsize=(16, 8), num=f"net_amount_by_branch_type_chart_{time.time()}")
        
        # Map branch types
        aggregated_sales["Branch Type"] = aggregated_sales["branchCode"].astype(str).apply(map_branch_type)

        # Group by Branch Type and sum Net Amount
        grouped_sales = aggregated_sales.groupby("Branch Type")["Net Amount"].sum().reset_index()

        # Sort by Net Amount
        grouped_sales = grouped_sales.sort_values(by="Net Amount", ascending=False)

        # Plot the bar chart
        bars = plt.bar(grouped_sales["Branch Type"], grouped_sales["Net Amount"], color="purple")

        # Adding labels above each bar
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 0.5,  
                    f"₹{int(yval):,}", ha="center", fontsize=12, fontweight="bold", color="black")

        plt.xlabel("Branch Type")
        plt.ylabel("Net Amount (₹)")
        plt.title(f"Net Amount by Branch Type (Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        
        # Save the chart to the provided buffer or path
        if isinstance(save_path, (str, os.PathLike)):
            plt.savefig(save_path, dpi=100)
        else:
            plt.savefig(save_path, format="png", dpi=100)
        return True
    except Exception as e:
        print(f"Error in plot_net_amount_by_branch_type_chart: {e}")
        return False
    finally:
        plt.close()
    
def plot_bill_cuts_by_branch_type_chart(aggregated_sales, save_path):
    try:
        plt.figure(figsize=(16, 8), num=f"bill_cuts_by_branch_type_chart_{time.time()}")
        
        # Map branch codes to Branch Types
        aggregated_sales["Branch Type"] = aggregated_sales["branchCode"].astype(str).apply(map_branch_type)

        # Group by Branch Type and sum Bill Cuts
        grouped_sales = aggregated_sales.groupby("Branch Type")["Bill Cuts"].sum().reset_index()

        # Sort by Bill Cuts
        grouped_sales = grouped_sales.sort_values(by="Bill Cuts", ascending=False)

        # Plot the bar chart
        bars = plt.bar(grouped_sales["Branch Type"], grouped_sales["Bill Cuts"], color="orange")

        # Adding labels above each bar
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2, yval + 1,  
                    f"{int(yval)}", ha="center", fontsize=12, fontweight="bold", color="black")

        plt.xlabel("Branch Type")
        plt.ylabel("Bill Cuts")
        plt.title(f"Bill Cuts by Branch Type (Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        
        # Save the chart to the provided buffer or path
        if isinstance(save_path, (str, os.PathLike)):
            plt.savefig(save_path, dpi=100)
        else:
            plt.savefig(save_path, format="png", dpi=100)
        return True
    except Exception as e:
        print(f"Error in plot_bill_cuts_by_branch_type_chart: {e}")
        return False
    finally:
        plt.close()

# Flask Route to serve all charts in one page with improved cache control
@app.route("/")
def serve_dashboard():
    # Use a timestamp for cache busting
    timestamp = int(time.time())
    
    return render_template_string(f"""
    <html>
    <head>
        <meta http-equiv="refresh" content="60">
        <title>Live Oyalo Sales Dashboard</title>
        <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
        <meta http-equiv="Pragma" content="no-cache">
        <meta http-equiv="Expires" content="0">
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ text-align: center; background-color: #f0f0f0; padding: 10px; }}
            h2 {{ margin-top: 30px; background-color: #e9e9e9; padding: 5px; }}
            .chart-container {{ text-align: center; margin-top: 10px; }}
            img {{ box-shadow: 0px 0px 10px rgba(0,0,0,0.1); max-width: 90%; }}
            .status-message {{ background-color: #e8f4f8; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>Live Oyalo Sales Dashboard</h1>
        <div class="status-message">
            Last Refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 
            Next Refresh: <span id="countdown">60</span> seconds
        </div>

        <h2>Table View</h2>
        <div class="chart-container">
            <img id="table-chart" src="/chart/table?t={timestamp}" width="80%">
        </div>

        <h2>Net Amount by Branch</h2>
        <div class="chart-container">
            <img id="net-amount-chart" src="/chart/net-amount?t={timestamp}" width="80%">
        </div>

        <h2>Bill Cuts by Branch</h2>
        <div class="chart-container">
            <img id="bill-cuts-chart" src="/chart/bill-cuts?t={timestamp}" width="80%">
        </div>
        
        <h2>Net Amount by Branch Type</h2>
        <div class="chart-container">
            <img id="net-amount-by-branch-type-chart" src="/chart/net-amount-by-branch-type?t={timestamp}" width="80%">
        </div>
        
        <h2>Bill Cuts by Branch Type</h2>
        <div class="chart-container">
            <img id="bill-cuts-by-branch-type-chart" src="/chart/bill-cuts-by-branch-type?t={timestamp}" width="80%">
        </div>
        
        <script>
            // Countdown timer for refresh
            let seconds = 60;
            const countdownElem = document.getElementById('countdown');
            setInterval(() => {{
                seconds -= 1;
                if (seconds <= 0) {{
                    seconds = 60;
                }}
                countdownElem.textContent = seconds;
            }}, 1000);
            
            // Function to refresh images
            function refreshImages() {{
                const timestamp = Date.now();
                document.querySelectorAll('img').forEach(img => {{
                    const src = img.src.split('?')[0];
                    img.src = `${{src}}?t=${{timestamp}}`;
                }});
            }}
            
            // Refresh images every 60 seconds
            setInterval(refreshImages, 60000);
        </script>
    </body>
    </html>
    """)

# Add chart serving routes with fallback to memory
@app.route("/chart/table")
def serve_table_chart():
    try:
        if os.path.exists(table_chart_path):
            response = send_file(table_chart_path, mimetype="image/png")
        else:
            # Fallback to in-memory version
            bytes_data = chart_memory_store.get("table")
            if bytes_data:
                response = Response(bytes_data, mimetype="image/png")
            else:
                return "Chart not available yet", 503
        
        # Add cache control headers
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"Error serving table chart: {e}")
        return "Error serving chart", 500

@app.route("/chart/net-amount")
def serve_net_amount_chart():
    try:
        if os.path.exists(net_amount_chart_path):
            response = send_file(net_amount_chart_path, mimetype="image/png")
        else:
            # Fallback to in-memory version
            bytes_data = chart_memory_store.get("net_amount")
            if bytes_data:
                response = Response(bytes_data, mimetype="image/png")
            else:
                return "Chart not available yet", 503
        
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"Error serving net amount chart: {e}")
        return "Error serving chart", 500

@app.route("/chart/bill-cuts")
def serve_bill_cuts_chart():
    try:
        if os.path.exists(bill_cuts_chart_path):
            response = send_file(bill_cuts_chart_path, mimetype="image/png")
        else:
            # Fallback to in-memory version
            bytes_data = chart_memory_store.get("bill_cuts")
            if bytes_data:
                response = Response(bytes_data, mimetype="image/png")
            else:
                return "Chart not available yet", 503
                
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"Error serving bill cuts chart: {e}")
        return "Error serving chart", 500

@app.route("/chart/net-amount-by-branch-type")
def serve_net_amount_by_branch_type_chart():
    try:
        if os.path.exists(net_amount_by_branch_type_chart_path):
            response = send_file(net_amount_by_branch_type_chart_path, mimetype="image/png")
        else:
            # Fallback to in-memory version
            bytes_data = chart_memory_store.get("net_amount_by_branch_type")
            if bytes_data:
                response = Response(bytes_data, mimetype="image/png")
            else:
                return "Chart not available yet", 503
                
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"Error serving net amount by branch type chart: {e}")
        return "Error serving chart", 500

@app.route("/chart/bill-cuts-by-branch-type")
def serve_bill_cuts_by_branch_type_chart():
    try:
        if os.path.exists(bill_cuts_by_branch_type_chart_path):
            response = send_file(bill_cuts_by_branch_type_chart_path, mimetype="image/png")
        else:
            # Fallback to in-memory version
            bytes_data = chart_memory_store.get("bill_cuts_by_branch_type")
            if bytes_data:
                response = Response(bytes_data, mimetype="image/png")
            else:
                return "Chart not available yet", 503
                
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    except Exception as e:
        print(f"Error serving bill cuts by branch type chart: {e}")
        return "Error serving chart", 500

# Health check endpoint to verify charts are updating correctly
@app.route("/health")
def health_check_endpoint():
    issues = []
    charts_available = 0
    
    # Check memory store first
    for chart_name in chart_memory_store:
        if chart_memory_store[chart_name]:
            charts_available += 1
    
    # Check disk charts
    chart_paths = [
        table_chart_path, 
        net_amount_chart_path, 
        bill_cuts_chart_path,
        net_amount_by_branch_type_chart_path, 
        bill_cuts_by_branch_type_chart_path
    ]
    
    for chart_path in chart_paths:
        if os.path.exists(chart_path):
            # Check file age
            # Continue from where the code was cut off
            mod_time = os.path.getmtime(chart_path)
            age_minutes = (time.time() - mod_time) / 60
            
            if age_minutes > 10:  # If chart is older than 10 minutes
                issues.append(f"Chart {os.path.basename(chart_path)} is {age_minutes:.1f} minutes old")
        else:
            issues.append(f"Chart file {os.path.basename(chart_path)} is missing")
    
    status = "OK" if charts_available == 5 and not issues else "WARNING"
    
    response_data = {
        "status": status,
        "charts_available": charts_available,
        "issues": issues,
        "last_check": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    return response_data

if __name__ == "__main__":
    # Create initial charts
    create_initial_charts()
    
    # Start the chart update thread
    chart_thread = threading.Thread(target=update_all_charts, daemon=True)
    chart_thread.start()
    
    # Run the Flask app
    print("Starting Flask server...")
    app.run(host="0.0.0.0", port=10000, debug=False)
