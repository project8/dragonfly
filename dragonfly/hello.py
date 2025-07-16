"""test Flask with this"""

from flask import Flask, redirect, request
app = Flask(__name__)

Slowdash_Pressures_URL = ('http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-Pressures.json') 

@app.route('/')
def hello():
    linkBakeout = '<a href="Bakeout">Baking out? Click me!</a><br>'
    linkExp = '<a href="Experimenting">Running an experiment? Click me!</a>'

    content = """
   <h1> Hello there!</h1>
   <h3> You are in a regular day (no Baking out, no experimenting) or else, click on the links at the end of the page </h3>
   <ul><p> <form action="/handle_data" method="post">

Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-CoolingLoopSensors.json">CoolingLoop Sensor</a>   <br>  
       <input type="checkbox" id="check1" name="check1" value="CoolingLoopSensor">
       <label for="check1"> Is the CoolingLoopSensor is running on Slowdash ? No flow = bad </label><br>
 Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">BC Thermocouples</a>   check all the temperatures <br> 
       <input type="checkbox" id="check2" name="check2" value="Thermocouples">
       <label for="check2"> Are the thermocouples temperature around 20C and below 25C? </label><br>
 Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">MainzAtomicTestStandPage</a> <br> 

       <input type="checkbox" id="check3" name="check3" value="MainzAtomicTestStandPage">
       <label for="check3"> Is there any red attention sign? If yes, dig into that </label><br>
       <input type="checkbox" id="check4" name="check4" value="Pressures">
       <label for="check4"> Go on this page: """ '<a href="test"> Click me!</a>'  """  check all the pressures  </label><br>
       <input type="checkbox" id="check5" name="check5" value="BC thermocouples">
       <label for="check5"> Go on this page:  <a href= "http://astro-wake.physik.uni-mainz.de:18881/slowplot.html?config=slowplot-ThermocoupleTemperatures.json">Slowdash</a>   check all the temperatures  </label>

       <input type="submit" value="Submit">
   </p> </form></ul>
    """
    return content + linkBakeout +linkExp 


@app.route('/handle_data', methods=['POST'])
def handle_data():
    print(request.form, flush=True)
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


