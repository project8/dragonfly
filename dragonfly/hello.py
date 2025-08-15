"""test Flask with this"""

from flask import Flask, redirect, request, render_template
from datetime import datetime
app = Flask(__name__)

Slowdash_Pressures_URL = ('http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-Pressures.json') 






listOfChecks = ["check1", "check2","check3","check4","check5"]#number of checks
Description = [' Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-CoolingLoopSensors.json">CoolingLoop Sensor</a>   <br> ','  Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">Brainbox Thermocouples</a> check all the temperatures <br>','Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">MainzAtomicTestStandPage</a> <br>','Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-Pressures.json">Pressures</a> <br>','' ] #what is displayed in the checklist's web page before each checkbox, such as a link for example
Labels = ['Is the Cooling Loop Sensor Ok? ie is there any flow',' Are the thermocouples temperature between 18C and 25C?',' Check if there is no red attention sign.','Check all the pressures','Go in the lab. Check if there is no weird sound '] # what is displayed in front of the checkbox
ResponseInElog = ["Cooling Loop Sensor","Brainbox thermocouples temperatures", "Red attention signs in Mainz Atomic Test Stand Page","Pressure", "Lab sounds"] #what will be written in the created eLog 

@app.route('/')
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
    <input type="text" id="UserName" name="UserName"><br> 
    <label for="UserName"> Who is filling the Checklist :</label> 
    """

    for check,text, label in zip(listOfChecks, Description, Labels):
        content += text
        content += f"""
        <input type="hidden" name="{check}_hidden" id="hiddenTerms_{check}">
        <input type="checkbox" id="{check}">
        <label for="{check}"> {label} </label> <br>
        """ 


    content += """
    <button type="submit" id="submit_button">Submit</button>
    </form>
    </p></ul>
    
    #in order to give the checkox a value if it was not checked
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

    print("Date and time is :"+ date_time, flush=True)
    print(request.form, flush=True)
    print("The one writing is : ",request.form["UserName"],flush=True)

    try :
        for check,response in zip(listOfChecks,ResponseInElog):
            if request.form.get(check+"_hidden")== 'True' :
                print("Checked", response ,"[x]",flush=True)
            else: 
                print("Checked",response, "[ ]", flush=True)

    except Exception as e:
        print(e)
   # print(dir(request.form),flush=True)

    # Tell the user that checklist is done.
    return "<h1> Thanks for filling out the check list. You are done for today. </h1>"


@app.route('/Bakeout')    #sends you on another one of the flask app page named Bakeout
def foobar():
    return '<h1>Baking out? No problem!</h1>'

@app.route('/test')
def test2():
    return {'url': 'http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-Pressures.json'}

@app.route('/Experimenting')
def foobar2():
    return '<h1>Running an experiment? No problem!</h1>'


