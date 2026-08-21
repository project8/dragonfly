from flask import Flask, redirect, request, render_template, url_for
import os
import yaml

CONFIG_FILE = "/root/AlarmSystem.yaml"

def load_data():
    if not os.path.exists(CONFIG_FILE):
        return []
    with open(CONFIG_FILE, "r") as open_file:
        config = yaml.safe_load( open_file )
        return config["check_endpoints"]

def save_data(data):
    with open(CONFIG_FILE, "r") as open_file:
        config = yaml.safe_load( open_file )
    config["check_endpoints"] = data
    print(config, flush=True)
    with open(CONFIG_FILE, "w") as open_file:
        yaml.safe_dump(config, open_file)

app = Flask(__name__)

@app.route('/')
def index():
    data = load_data()
    
    return render_template("index.html", data=data)

@app.route('/add', methods=["POST"])
def add_row():
    data = load_data()

    
    new_row = { 
        "enable": request.form.get("enable") == "on",
        "endpoint": request.form.get("endpoint"),
        "method": request.form.get("comparison"),
        "reference": request.form.get("reference"),
        "message": request.form.get("message"),
    }
    try:
        new_row["reference"] = float(new_row["reference"])
    except:
        pass

    data.append(new_row)

    save_data(data)

    return redirect(url_for("index"))

@app.route("/delete/<int:index>", methods=["POST"])
def delete_row(index):
    data = load_data()

    if 0 <= index < len(data):
        data.pop(index)

    save_data(data)

    return redirect(url_for("index"))

@app.route("/update", methods=["POST"])
def update():
    data = load_data()

    for i, row in enumerate(data):
        row["enable"] = request.form.get(f"enable_{i}") == "on"
        row["endpoint"] = request.form.get(f"endpoint_{i}")
        row["comparison"] = request.form.get(f"comparison_{i}")
        row["reference"] = request.form.get(f"reference_{i}")
        try:
            row["reference"] = float(row["reference"])
        except:
            pass
        row["message"] = request.form.get(f"message_{i}")

    save_data(data)

    return redirect(url_for("index"))
