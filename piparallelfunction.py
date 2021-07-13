#!/usr/bin/env python3
# https://cloud.google.com/appengine/docs/standard/python3/using-python3-libraries python3 support for deployment from lab1

import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, Executor
from botocore.credentials import SharedCredentialProvider
import time
import math
import os
import logging
from flask import Flask, request, render_template, copy_current_request_context
import json as JSON
import cgitb
import cgi
import requests


resources = None
shots = None
digits = None
reporting_rate = None
resources2 = None
incircle = None
piestimation = None
closest_pi = None
PublicDns_names = []
instance_ids = []
records = []
recordsec2 = []
History = []
timetaken = []
timetakenlambda = []
timetakenec2 = []
costlambda = None
costec2 = None

cgitb.enable()


app = Flask(__name__)
os.environ['AWS_DEFAULT_REGION'] = 'eu-west-2'


def doRender(tname, values={}):
    if not os.path.isfile(os.path.join(os.getcwd(), 'templates/'+tname)):  # No such file
        return render_template('random.htm')
    return render_template(tname, **values)


############## calculate the values of pi using AWS LAMBDA ###################

@app.route('/piestimation', methods=['POST'])
def piestimation():
    global resources
    global shots
    global digits
    global reporting_rate
    global records
    global History
    resources = request.form.get('resources', default=6, type=int)
    shots = request.form.get('shots', type=int)
    digits = request.form.get('digits', default=6, type=int)
    reporting_rate = request.form.get('reportingrate', default=1000, type=int)

    target = float(str(math.pi)[:digits+2])
    iterations = int(shots/(reporting_rate*resources))
    sets = iterations

    startingtime = time.time()

    def lambdaHandler(self):
        global History
        global timetaken
        global timetakenlambda
        global costlambda
        import http.client
        awslambda = "l1v0r8ksm4.execute-api.us-east-1.amazonaws.com"
        c = http.client.HTTPSConnection(awslambda)
        msg = '{ "key1": "'+str(reporting_rate)+'"}'

        c.request("POST", "/beta/Function1CW", msg)
        response = c.getresponse()
        awslambda = JSON.loads(
            response.read().decode('utf-8'))

        incircle = float(awslambda['incircle'])
        piestimation = float(awslambda['piestimate'])
        totaltime = time.time() - startingtime
        timetaken.append(totaltime)
        timetakenlambda.append(timetaken[-1])
        return (incircle, piestimation, totaltime)

    runs = [value for value in range(resources)]
    values = []
    pi_values = []
    Batch = {}
    executor = ThreadPoolExecutor()
    with ThreadPoolExecutor() as executor:
        for i in range(iterations):
            results = executor.map(lambdaHandler, runs)
            global records
            global History
            # loop only once in generator object
            data = [result for result in results]
            total_incircle = sum([datain[0] for datain in data])
            total_shots = str(reporting_rate*resources)
            pi_data = [datin[1] for datin in data]

            # save averages pi values in a list
            avg_pi = sum(pi_data)/len(pi_data)
            values.append(avg_pi)

            # store moving averages in a list
            pi_values.append(sum(values[:i+1])/(i+1))

            # store batch numbers
            Batch = i+1

            records.append((Batch, total_incircle, total_shots, avg_pi))

            # BREAKING THEE LOOP ONCE THE REQUIREMENTS ARE MET
            if float(str(pi_values[-1])[:digits+2]) == target:
                break
            else:
                iterations += sets

    legend = 'Pi-Estimation'
    labels = [reporting_rate*resources*(i+1)
              for i in range(len(pi_values))]

    targetvalues = [math.pi] * iterations

    # finding the closest value of pi in moving averages
    def absolute_difference(pivalue): return abs(pivalue-math.pi)
    closest_pi = min(pi_values, key=absolute_difference)

    # cost calculation : Total Compute (Gb-s) = [Number of executions]*[Time for each execution]*[Total compute (GB-s)]
    print(timetakenlambda[-1])
    cost = (timetakenlambda[-1])*iterations*(128/1024)
    # calculating billable cost = Total Compute(GB-s)*compute price($0.00001667)
    costlambda = cost * (0.00001667)
    History.append((resources, shots, digits,
                   reporting_rate, costlambda, closest_pi))

    return doRender('lambda.htm', {'records': records, 'History': History, 'shots': shots, 'reporting_rate': reporting_rate, 'resources': resources, 'digits': digits, 'closest_pi': closest_pi, 'my_values': pi_values, 'labels': labels, 'legend': legend, 'pi': targetvalues})


############## calculate the values of pi using AWS EC2  ###################
@ app.route('/create_ec2instances', methods=['POST'])
def create_ec2instances():
    global resources2
    resources2 = request.form.get('resources', default=6, type=int)
    starttimeec2 = time.time()
    os.environ['AWS_SHARED_CREDENTIALS_FILE'] = './cred'
    import boto3
    print("creating EC2 instances...")
    ec2 = boto3.resource('ec2')
    create_instances = ec2.create_instances(
        ImageId="ami-0ced801df4c59cb6c",
        MinCount=1,
        MaxCount=resources2,
        InstanceType="t2.micro",
        KeyName="piestimates",
        SecurityGroups=['SSH'])

    global PublicDns_names
    global instance_ids
    for instances in create_instances:
        instances.wait_until_running()
        instances.load()
        PublicDns_names.append(instances.public_dns_name)
        instance_ids.append(instances.id)

    timetakenec2 = time.time() - starttimeec2
    return doRender('EC2.htm', {'note': timetakenec2, 'PublicDns_names': PublicDns_names, 'instance_ids': instance_ids})


@ app.route('/ec2piestimation', methods=['POST'])
def ec2piestimation():
    global shots
    global digits
    global reporting_rate
    global History
    shots = request.form.get('shots', type=int)
    digits = request.form.get('digits', default=6, type=int)
    reporting_rate = request.form.get('reportingrate', default=1000, type=int)

    target = float(str(math.pi)[:digits+2])
    iterations = int(shots/(reporting_rate*resources2))

    startingtime = time.time()

    def ec2Handler(self):
        global incircle
        global piestimation
        global recordsec2
        global History
        global timetaken
        global timetakenec2
        for x in range(0, iterations):
            for i in PublicDns_names:
                final_url = "http://" + i + \
                    "/postform.py?"+str(reporting_rate)+""

            response = requests.get(final_url, verify=False)
            ec2data = response.content
            ec2data = ec2data.decode("utf-8")
            ec2data = ec2data.split()
            incircle = float(ec2data[1])
            piestimation = float(ec2data[0])
            totaltime = time.time() - startingtime
            timetaken.append(totaltime)
            timetakenec2.append(timetaken[-1])
            return(incircle, piestimation, timetaken)

    runs = [value for value in range(resources2)]
    values = []
    pi_values = []
    Batch = []
    executor = ThreadPoolExecutor()
    with ThreadPoolExecutor() as executor:
        for i in range(iterations):
            results = executor.map(ec2Handler, runs)
            global recordsec2
            global costec2
            # loop only once in generator object
            data = [result for result in results]
            total_incircle = sum([datain[1] for datain in data])
            total_shots = reporting_rate*resources2
            pi_data = [datin[0] for datin in data]

            # save averages pi values in a list
            avg_pi = sum(pi_data)/len(pi_data)
            values.append(avg_pi)

            Batch = i+1

            # store moving averages in a list
            pi_values.append(sum(values[:i+1])/(i+1))

            recordsec2.append((Batch, total_incircle, total_shots, avg_pi))

            # BREAKING THEE LOOP ONCE THE REQUIREMENTS ARE MET
            if float(str(pi_values[-1])[:digits+2]) == target:
                break

    legend = 'Pi-Estimation'
    labels = [reporting_rate*resources2*(i+1)
              for i in range(len(pi_values))]

    targetvalues = [math.pi] * iterations

    # finding the closest value of pi in moving averages
    def absolute_difference(pivalue): return abs(pivalue-math.pi)
    closest_pi = min(pi_values, key=absolute_difference)

    # EC2 cost estimate
    # Cost/Hr for 1 EC2 t2.micro instance is 0.0116$
    # Therefore Cost/sec = 0.0116/3600
    # Totalcost = [time in seconds]*[Number of resources]*[cost/second]-
    # time taken to create and terminate instances are neglicted as costs are calculated based on run time for estimations alone.
    costec2 = (timetakenec2[-1])*(resources2)*(0.0116/3600)

    History.append((resources2, shots, digits,
                   reporting_rate, costec2, closest_pi))

    return doRender('EC2.htm', {'records': recordsec2, 'History': History, 'shots': shots, 'reporting_rate': reporting_rate, 'resources': resources, 'digits': digits, 'closest_pi': closest_pi, 'my_values': pi_values, 'labels': labels, 'legend': legend, 'pi': targetvalues})


@ app.route('/terminateinstances', methods=['POST'])
def terminate_ec2_instances():
    try:
        print("Terminate EC2 instance")
        import boto3
        ec2 = boto3.client("ec2")
        ec2.terminate_instances(InstanceIds=instance_ids)
    except Exception as e:
        print(e)

    return doRender('random.htm')


@ app.route('/history', methods=['POST'])
def show_history():
    return doRender('history.htm', {'History': History, 'shots': shots, 'reporting_rate': reporting_rate, 'resources': resources, 'digits': digits, 'closest_pi': closest_pi})
################################################################################################################################
# catch all other page requests - doRender checks if a page is available (shows it) or not (index)


@ app.route('/', defaults={'path': ''})
@ app.route('/<path:path>')
def mainPage(path):
    return doRender(path)


@ app.errorhandler(500)
# A small bit of error handling
def server_error(e):
    logging.exception('ERROR!')
    return """
    An  error occurred: <pre>{}</pre>
    """.format(e), 500


if __name__ == '__main__':
    # Entry point for running on the local machine
    # On GAE, endpoints (e.g. /) would be called.
    # Called as: gunicorn -b :$PORT index:app,
    # host is localhost; port is 8080; this file is index (.py)
    app.run(host='127.0.0.1', port=8080, debug=True)
