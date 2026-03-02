from flask import Flask, redirect, request, render_template
from datetime import datetime
from dragonfly.utility import send_to_elog
import yaml

with open("/root/checklist.yaml", "r") as open_file:
    config = yaml.safe_load( open_file.read() )

app = Flask(__name__)

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
