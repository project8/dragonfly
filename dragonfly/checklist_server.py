from flask import Flask, redirect, request, render_template
from datetime import datetime
from dragonfly.utility import send_to_elog
import yaml

with open("/root/checklist.yaml", "r") as open_file:
    config = yaml.safe_load( open_file.read() )

app = Flask(__name__)

Slowdash_Pressures_URL = ('http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-Pressures.json') 
listOfChecks = ["check1", "check2","check3","check4","check5"]
Description = [' Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-CoolingLoopSensors.json">CoolingLoop Sensor</a>   <br> ','  Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">Brainbox Thermocouples</a> check all the temperatures <br>','Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">MainzAtomicTestStandPage</a> <br>','' ,'Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-Pressures.json">Slowdash Pressures</a> <br>'] #what is displayed in the checklist's web page before each checkbox, such as a link for example
Labels = ['Is the Cooling Loop Sensor Ok? ie is there any flow',' Are the thermocouples temperature between 18C and 25C?',' Check if there is no red attention sign.','Go in the lab. Check if there is no weird sound ','Check all the pressures'] # what is displayed in front of the checkbox
ResponseInElog = ["Cooling Loop Sensor","Brainbox thermocouples temperatures", "Red attention signs in Mainz Atomic Test Stand Page", "Lab sounds","Pressures"] #what will be written in the created eLog 

PressureGauges = ["PG80", "PG90"]#name of the Pressure Gauge
ValueOfPG = ["Should be between 1e-10 hPa and 2e-9 hPa", "Should be between 1e-10hPa and 2e-9 hPa"]# range of the value the corresponding PG should have

@app.route('/')
def select_list():
    content = ""
    content += "<h1> Please select a Checklist </h1>"
    for checklist in config["checklists"]:
        label = checklist["name"]
        url_name = label.replace(" ", "_")
        content += f'<a href="checklist/{url_name}"> {label} </a> <br>'
    return content

@app.route('/checklist/<checklist_name>')
def show_checklist(checklist_name):
    checklist = None
    for c in config["checklists"]:
        if checklist_name == c["name"].replace(" ", "_"):
            checklist = c
    if checklist is None:
        return f'Checklist for {checklist_name} not found. Go back to <a href="/"> start page</a>'

    content = """
              <h1> {title} </h1>
              <p> <form id="checklist" action="/submit/{checklist_name}" method="post">
              <input type="hidden" id="checklist_name" name="checklist_name" value="{title}" />
              User: <input type="text" id="user" name="user"> <br> <br>
              {questions}
              <button type="submit" id="submit_button"> Submit Checklist </button>
              </form> </p>

              <script>
                 const form = document.getElementById('checklist');
                 const button = document.getElementById('submit_button');
                 {checkbox_script}
              </script>
              """
    title = checklist['name']
    questions = ""
    checkbox_script = ""

    for i, question in enumerate(checklist["questions"]):
        if question["type"] == "text":
            if "label_checklist_pre" in question.keys():
                questions += f'{question["label_checklist_pre"]}: '
            questions += f'<input type"text" id="question_{i}" name="question_{i}">'
            if "label_checklist_post" in question.keys():
                questions += f'<label for"question_{i}"> {question["label_checklist_post"]} </label>'
        elif question["type"] == "checkbox":
            label = f"{i}"
            questions += f'<input type="hidden" id="hidden_{i}" name="hidden_{i}"> <input type="checkbox" id="question_{i}"> '
            if "label_checklist" in question.keys():
                questions += f'<label for="question_{i}"> {question["label_checklist"]} </label>'
            checkbox_script += f"""const checkbox_{i} = document.getElementById("question_{i}"); 
                                   const hidden_{i} = document.getElementById("hidden_{i}"); """
            checkbox_script += "button.addEventListener('click', () => { hidden_%d.value = checkbox_%d.checked ? 'True' : 'False'; }); "%(i,i)
        if "link_page" in question.keys():
            questions += f'<a target="_blank" rel="noopener noreferrer" href="{question["link_page"]}">Check on this page.</a>'
        questions += '<br><br>'
    return content.format(title=title, checklist_name=checklist_name, questions=questions, checkbox_script=checkbox_script)


@app.route('/submit/<checklist_name>', methods=["GET",'POST'])
def submit_checklist(checklist_name):
    # This function is called with the result of the check list.
    # Use the request.form content to generate a nice ELOG message
    # That elog message will be posted to the elog
    
    checklist = None
    for c in config["checklists"]:
        if checklist_name == c["name"].replace(" ", "_"):
            checklist = c
    if checklist is None:
        return f'Checklist for {checklist_name} not found. Go back to <a href="/"> start page</a>'


    report = ""
    try:
        report += f"Timestamp: %s\n"%(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
        report += f"User: {request.form['user']}\n"
        for i, question in enumerate(checklist["questions"]):
            if question["type"] == "text":
                report = report + question["label_elog"] + ": " + request.form.get(f"question_{i}") + "\n"
            elif question["type"] == "checkbox":
                if request.form.get(f"hidden_{i}") == 'True':
                    report += f"[x] {question['label_elog']}\n"
                else:
                    report += f"[ ] {question['label_elog']}\n"
    except Exception as e:
        print(e, flush=True)

    print(report, flush=True)
    send_to_elog(report, subject=checklist_name, author=config["username"], category="Slow controls", msg_id=None, password=config["password"])

    # Tell the user that checklist is done.
    return '<h1> Checklist successfully submitted. You can go back to the <a href="/"> start page </a>. </h1>'

@app.route('/hello')
def hello():
    linkBakeout = '<a href="Bakeout">Baking out? Click me!</a><br>'
    linkExp = '<a href="Experimenting">Running an experiment? Click me!</a>'

    now = datetime.now() # current date and time
    date_time = now.strftime("%d/%m/%Y, %H:%M:%S")


    content = """
    <h1> Hello there!</h1>
    <h3> You are in a regular day (no Baking, no experimenting). If you are not, please click on the links at the end of the page. </h3>

    <ul><p> 
    <form id="Checklist" action="/handle_data" method="post">
    Who is filling the Checklist : 
    <input type="text" id="UserName" name="UserName"> <br><br>
    """

    for check,text, label in zip(listOfChecks, Description, Labels):
        content += text
        content += f"""
        <input type="hidden" name="{check}_hidden" id="hiddenTerms_{check}">
        <input type="checkbox" id="{check}">
        <label for="{check}"> {label} </label> <br><br>
        """ 

    for PG,labelOfPG in zip(PressureGauges,ValueOfPG,) : 
        content += PG + """ :"""
        content += f"""
        <input type="text" id="{PG}" name="{PG}"> 
        <label for="{PG}"> {labelOfPG} </label><br> 

        """

    content += """
    <button type="submit" id="submit_button">Submit</button>
    </form>
    </p></ul>

    <script> 
        const form = document.getElementById('Checklist');
        const button = document.getElementById('submit_button');
    """
    for i, check in enumerate(listOfChecks):
        content += f"""
        const checkbox_{i} = document.getElementById("{check}");
        const hidden_{i} = document.getElementById("hiddenTerms_{check}");
        """
        content += """
        button.addEventListener('click', () => { hidden_%d.value = checkbox_%d.checked ? 'True' : 'False'; }); 
        """%(i,i)
    content += """
    </script> 
    """

    return date_time +content + linkBakeout +linkExp 


@app.route('/handle_data', methods=["GET",'POST'])
def handle_data():
    # This function is called with the result of the check list.
    # Use the request.form content to generate a nice ELOG message
    # That elog message will be posted to the elog

    now = datetime.now() # current date and time
    date_time = now.strftime("%d/%m/%Y, %H:%M:%S")

    report = ""
    report += f"Date and time is: {date_time}\n"
    report += f"The one writing is: {request.form['UserName']}\n"
    try:
        for check, response in zip(listOfChecks, ResponseInElog):
            if request.form.get(f"{check}_hidden") == 'True':
                report += f"Checked {response} [x]\n"
            else:
                report += f"Checked {response} [ ]\n"

        for namePG in PressureGauges:
            report += f"The value of %s is: %s\n"%(namePG, request.form[f"{namePG}"])

    except Exception as e:
        print(e)

    send_to_elog(report, subject="Checklist", author=config["username"], category="Slow controls", msg_id=None, password=config["password"])

    # Tell the user that checklist is done.
    return "<h1> Thanks for filling out the check list. You are done for today. </h1>"


@app.route('/Bakeout')    #sends you on another one of the flask app page named Bakeout
def foobar():
    return '<h1>Baking out? No problem!</h1>'


@app.route('/Experimenting')
def foobar2():
    return '<h1>Running an experiment? No problem!</h1>'


