#This class implements a client to interact with
#the REST Api of LogServer.py
import requests
from requests.auth import HTTPBasicAuth
import datetime
from getmac import get_mac_address
from loguru import logger 

class LogClient:
    '''
    New LogClient for python based measurements

    Usage:
        from WebCtrlLogClient import LogClient
        import time

        cl=LogClient(host='http://127.0.0.1:5000/')

        # initialize your device with device type
        devType='GEN'
        version='1.0'
        cl.initDevice(devType,version)

        while True:
            # measurement ids of all active measurements
            for measId in cl.getActiveMeasurements():
                # run your measurement with the parameters specified in the web interface
                parameters=cl.getMeasurementOptions(measId) # dict according to ESPMeasurements.yml
                val=measure(parameters)

                # upload your measured value with the measurement id
                cl.addLog(measId,val) 

            # ping LogServer to stay online and update measurement parameters
            # run once per second
            cl.onlinePing() 
            time.sleep(1)
    '''
    def __init__(self,host='http://127.0.0.1:5000/'): 
        self.log=logger.bind(component="Lakeshore340")
        #self.log.setLevel(logging.INFO)#.INFO)#
        self.log.info('Logging initialized')

        self.host=host
        self.deviceId=-1

        self.measUpdated=True # indicates if a measurement updated since last get
        self.activeMeasurements=[]
        self.measurements={}


    def initDevice(self,devType,version):
        '''
        Initiates comunication and gets device id with mac address and version
        this also initiates a new device
        '''
        self.log.info("Initializing device with MAC: "+get_mac_address()+", Type: '%s', Version: '%s'" % (devType,str(version)))
        path="/devIdGeneral?macAddr="+get_mac_address()+"&devType=%s&version=%s" % (devType,str(version))
        result=self.getRequest(path)
        devId=result['DeviceId']
        self.deviceId=devId

        self.updateMeasurments()
        return devId

    def onlinePing(self):
        '''
        Ping LogServer to check for changed parameters
        Needs to run once per second

        returns 1 if any parameter changed
                0 if not
        '''
        self.log.trace('Ping to LogServer')
        path="status?deviceId="+str(self.deviceId)
        result=self.getRequest(path)
        updated=result['Update']

        if updated>0:
            self.log.info('Measurement update detected')
            self.updateMeasurments()
        return updated

    def getActiveMeasurements(self):
        '''
        returns list with measurementIds of active measurements of this device
        '''
        return self.activeMeasurements

    def getMeasurementOptions(self,measId):
        '''
        returns options of measurement with measId
        '''
        self.measUpdated=False
        return self.measurements.get(measId)

    def addLog(self,measId,value):
        data = {}
        data['MeasId']=int(measId)
        data['Value']=value

        path="log/1"
        result=self.putRequest(path,data)
        return int(result)

    def getLog(self,measId):
        path="log/"+str(int(measId)) 
        result=self.getRequest(path)
        return result

    def putRequest(self,path,data):
        req=requests.put(self.host+path,json=data,verify=False)
        self.log.trace("PUT '"+path+"' "+str(req.status_code))
        req.raise_for_status()
        return req.json()

    def getRequest(self,path):
        if(path[0]=='/'):
            path=path[1:]
        req=requests.get(self.host+path,verify=False)
        self.log.trace("GET '"+path+"' "+str(req.status_code))
        req.raise_for_status()
        return req.json()
        
    def raiseError(self,devId,code):
        # Only debugging, testing error class in LogServer by raising ESP32 device error
        data ={}
        data['DevId']=int(devId)
        data['Code']=int(code)
        
        path="error/1"
        result=self.putRequest(path,data)
        return result

    def updateMeasurments(self):
        '''
        updates active measurements from LogServer
        '''
        self.log.info('Updating measurements')

        # get number of active measurements
        path="/activeMeasurements?deviceId="+str(self.deviceId)
        result=self.getRequest(path)
        nActMeasurements=result['ActiveMeasurements']

        actMeas=[]
        path="/measOptions?deviceId="+str(self.deviceId)
        for i in range(0,nActMeasurements):
            result=self.getRequest(path+"&nb="+str(i))
            actMeas.append(result['MeasId'])
            self.measurements[result['MeasId']]=result
        self.activeMeasurements=actMeas
        self.measUpdated=True



