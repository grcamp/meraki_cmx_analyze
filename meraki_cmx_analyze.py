#!/usr/bin/env python
#########################################################################
# Gregory Camp
# grcamp@cisco.com
# meraki_cmx_analyze.py takes a CSV file of observations from the Meraki
#    CMX cloud push API and prints the client visit output and CMX API
#    Analytics.
#
# This script takes section 2 of the link below and builds per site
#   Proximity, Engagement, and Loyalty data.
#
# https://documentation.meraki.com/MR/Monitoring_and_Reporting/CMX_Analytics
#
# Usage:
#   The script looks for data in a CSV format as listed below:
#   Site,AP Mac,Client Mac,IPv4,IPv6,Event Time ISO, \
#       Event Time Epoch,SSID,RSSI,Manufacturer,Operating System
#
#########################################################################

import sys,os,time,operator,datetime

#########################################################################
# Class Observation
#
# Container is for importing the raw observations from the input file
#########################################################################
class Observation:
    # Method __init__ initializes the class variables
    #
    # Input: None
    # Output: None
    # Parameters: 
    #
    # Return Value: None
    #####################################################################
    def __init__(self, apMac, clientMac, ipv4, ipv6, seenTime, seenEpoch, ssid, rssi, manufacturer, os):
        self.apMac = apMac
        self.clientMac = clientMac
        self.ipv4 = ipv4
        self.ipv6 = ipv6
        self.seenTime = seenTime
        self.seenEpoch = long(seenEpoch)
        self.ssid = ssid
        self.rssi = long(rssi)
        self.manufacturer = manufacturer
        self.os = os
        self.partOfVisit = False
        self.connected = False
        
        # If you have an SSID set, you must be connected
        if self.ssid != "":
            self.connected = True
        

    # Method to_string builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def to_string(self):
        returnString = ""
        returnString = returnString + self.apMac + ','
        returnString = returnString + self.clientMac + ','
        returnString = returnString + self.ipv4 + ','
        returnString = returnString + self.ipv6 + ','
        returnString = returnString + self.seenTime + ','
        returnString = returnString + str(self.seenEpoch) + ','
        returnString = returnString + self.ssid + ','
        returnString = returnString + str(self.rssi) + ','
        returnString = returnString + self.manufacturer + ','
        returnString = returnString + self.os
        return returnString

#########################################################################
# Class Client
#
# Container to identify Clients that have connected to a network
#########################################################################
class Client:
    # Method __init__ initializes the class variables
    #
    # Input: None
    # Output: None
    # Parameters: 
    #
    # Return Value: None
    #####################################################################
    def __init__(self, clientMac):
        self.clientMac = clientMac
        self.observations = []
        self.visits = []
        self.manufacturer = ""
        self.os = ""
        
    # Method add_observation takes the passed observation and appends items
    #   to the current list of observations owned by the client
    #
    # Input: None
    # Output: None
    # Parameters:
    #   newObservation - observation to add to the list for the client
    #
    # Return Value: None
    #####################################################################
    def add_observation(self, newObservation):
        # Add observation to list
        self.observations.append(newObservation)

        return None

    # Method is_passerby checks if the client was seen during a specific
    #   time window
    #
    # Input: None
    # Output: None
    # Parameters:
    #   startTimeEpoch - Start of search window
    #   endTimeEpoch - End of search window
    #
    # Return Value: None
    #####################################################################
    def is_passerby(self, startTimeEpoch, endTimeEpoch):
        # For each observation in the list, look if the epoch time matches
        for observation in self.observations:
            # If observation falls into the window return True
            if (observation.seenEpoch >= startTimeEpoch) and (observation.seenEpoch <= endTimeEpoch):
                return True

        return False
    
    # Method is_visitor
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def is_visitor(self, startTimeEpoch, endTimeEpoch):
        for visit in self.visits:
            if (visit.startTimeEpoch >= startTimeEpoch) and (visit.startTimeEpoch <= endTimeEpoch):
                return True
            elif (visit.endTimeEpoch >= startTimeEpoch) and (visit.endTimeEpoch <= endTimeEpoch):
                return True

        return False
    
    # Method is_connected
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def is_connected(self, startTimeEpoch, endTimeEpoch):
        for visit in self.visits:
            if (visit.startTimeEpoch >= startTimeEpoch) and (visit.startTimeEpoch <= endTimeEpoch) and (visit.connected == True):
                return True
            elif (visit.endTimeEpoch >= startTimeEpoch) and (visit.endTimeEpoch <= endTimeEpoch) and (visit.connected == True):
                return True

        return False

    # Method get_visits builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def get_visits(self, networkName):
        returnString = ""

        for visit in self.visits:
            returnString = returnString + networkName + "," + self.clientMac + "," + visit.to_string() + "\n"
        
        return returnString

    # Method discover_visits builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def discover_visits(self, observationsPerWindow, window, minStartRSSI, minSessionRSSI):
        # Declare variables
        i = 0
        maxIndex = len(self.observations) - 1
        
        # Sort observations
        self.observations.sort(key=operator.attrgetter('seenEpoch'))
        
        while i <= maxIndex:
            self._find_visits(i, observationsPerWindow, window, minStartRSSI, minSessionRSSI)
            i = i + 1

        i = 0

        while i <= maxIndex:
            i = self._build_visits(i, window)
        
        # Sort visits
        self.visits.sort(key=operator.attrgetter('startTimeEpoch'))
        
        return None

    # Method _find_visit builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def _find_visits(self, startIndex, observationsPerWindow, window, minStartRSSI, minSessionRSSI):
        # Declare variables
        maxIndex = len(self.observations) - 1
        i = 0
        eventCount = 0
    
        if (self.observations[startIndex].connected == False) and (self.observations[startIndex].rssi < minStartRSSI):
            return None
        
        if startIndex + i > maxIndex:
            return None
        
        # Search list until epoch time is current observation time + window
        while (self.observations[startIndex + i].seenEpoch <= self.observations[startIndex].seenEpoch + window):
            if (self.observations[startIndex + i].rssi >= minSessionRSSI) or (self.observations[startIndex + i].connected == True):
                eventCount = eventCount + 1

            i = i + 1

            if startIndex + i > maxIndex:
                break
        
        i = 0
        
        if eventCount >= observationsPerWindow:
            # Search list until epoch time is current observation time + window
            while (self.observations[startIndex + i].seenEpoch <= self.observations[startIndex].seenEpoch + window):
                self.observations[startIndex + i].partOfVisit = True
                
                i = i + 1

                if startIndex + i > maxIndex:
                    break
                
        return None

    # Method _build_visits builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def _build_visits(self, startIndex, window):
        # Declare variables
        maxIndex = len(self.observations) - 1
        i = startIndex
        
        if self.observations[i].partOfVisit == True:
            newVisit = Visit(self.observations[i].seenEpoch, self.observations[i].seenEpoch)
            self.visits.append(newVisit)
    
            while (self.observations[i].partOfVisit == True) and (self.observations[i].seenEpoch - window <= newVisit.endTimeEpoch):
                newVisit.endTimeEpoch = self.observations[i].seenEpoch
                
                if self.observations[i].connected == True:
                    newVisit.connected = True
                
                i = i + 1
                
                if i > maxIndex:
                    break
            
            newVisit.length = newVisit.endTimeEpoch - newVisit.startTimeEpoch
        else:
            i = i + 1
        
        return i

    # Method get_observations builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def get_observations(self, networkName):
        returnString = ""
        
        for observation in self.observations:
            returnString = returnString + networkName + "," + observation.to_string() + "\n"

        return returnString

#########################################################################
# Class Network
#
# 
#########################################################################
class Network:
    # Method __init__ initializes the class variables
    #
    # Input: None
    # Output: None
    # Parameters: 
    #
    # Return Value: None
    #####################################################################
    def __init__(self, name):
        self.name = name
        self.clients = []

    # Method _find_client
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def _find_client(self, clientMac):
        for client in self.clients:
            if clientMac == client.clientMac:
                return client
        
        return Client("")
    
    # Method get_cmx_proximity_report
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def get_cmx_proximity_report(self, startTimeEpoch, endTimeEpoch):
        # Declare variables
        currentDate = ""
        report = ""
    
        currentDate = epochtime_to_datetime(startTimeEpoch,'%Y-%m-%d')

        report = self.name + "," + currentDate + "," + self._cmx_find_client_proximity(startTimeEpoch, endTimeEpoch)
        
        return report
    
    # Method _cmx_proximity_report
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def _cmx_find_client_proximity(self, startTimeEpoch, endTimeEpoch):
        returnString = ""
        passerbyCount = 0
        visitorCount = 0
        connectedCount = 0
        captureRate = 0

        for client in self.clients:
            
            if client.is_passerby(startTimeEpoch, endTimeEpoch) == True:
                passerbyCount = passerbyCount + 1
            
            if client.is_visitor(startTimeEpoch, endTimeEpoch) == True:
                visitorCount = visitorCount + 1
            
            if client.is_connected(startTimeEpoch, endTimeEpoch) == True:
                connectedCount = connectedCount + 1
        
        passerbyCount = passerbyCount - visitorCount
        
        captureRate = float(connectedCount) / float(visitorCount)
        captureRate = captureRate * 100
        captureRate = long(round(captureRate, 0))
        
        returnString = str(passerbyCount) + "," + str(visitorCount) + "," + str(connectedCount) + "," + str(captureRate)
        return returnString
    
    # Method get_cmx_engagement_report
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def get_cmx_engagement_report(self, startTimeEpoch, endTimeEpoch):
        # Declare variables
        currentDate = ""
        report = ""
    
        currentDate = epochtime_to_datetime(startTimeEpoch,'%Y-%m-%d')

        report = (self.name + "," + currentDate + "," + self._cmx_find_visits_of_length(startTimeEpoch, endTimeEpoch, 300, 1200) + "," +
            self._cmx_find_visits_of_length(startTimeEpoch, endTimeEpoch, 1200, 3600) + "," +
            self._cmx_find_visits_of_length(startTimeEpoch, endTimeEpoch, 3600, 21600) + "," +
            self._cmx_find_visits_of_length(startTimeEpoch, endTimeEpoch, 21600, 86400))
            
        
        return report
    
    # Method _cmx_count_visits_of_length
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def _cmx_find_visits_of_length(self, startTimeEpoch, endTimeEpoch, lengthMin, lengthMax):
        visitCount = 0
        myStartTime = 0
        myEndTime = 0

        for client in self.clients:
            for visit in client.visits:
                myStartTime = 0
                myEndTime = 0
        
                if (visit.startTimeEpoch < startTimeEpoch) and (visit.endTimeEpoch > endTimeEpoch):
                    break
                elif (visit.startTimeEpoch < startTimeEpoch) and (visit.endTimeEpoch <= endTimeEpoch):
                    myStartTime = startTimeEpoch
                    myEndTime = visit.endTimeEpoch
                elif (visit.startTimeEpoch >= startTimeEpoch) and (visit.endTimeEpoch > endTimeEpoch):
                    myStartTime = visit.startTimeEpoch
                    myEndTime = endTimeEpoch
                else:
                    myStartTime = visit.startTimeEpoch
                    myEndTime = visit.endTimeEpoch

                if (myEndTime - myStartTime >= lengthMin) and (myEndTime - myStartTime < lengthMax):
                    visitCount = visitCount + 1

        return str(visitCount)

    # Method get_cmx_loyalty_report
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def get_cmx_loyalty_report(self, startTimeEpoch, loyaltyStartEpoch, loyaltyEndEpoch, timeIterator):
        # Declare variables
        currentTimeEpoch = startTimeEpoch
        currentDate = ""
        report = ""
        occasionalVisitors = 0
        dailyVisitors = 0
        firstTimeVisitors = 0
    
        currentDate = epochtime_to_datetime(startTimeEpoch,'%Y-%m-%d')
        
        for client in self.clients:
            if client.is_visitor(currentTimeEpoch, currentTimeEpoch + timeIterator - 1) == True:
                myTimeEpoch = loyaltyStartEpoch
                myVisitCount = 0
                
                while myTimeEpoch < loyaltyEndEpoch:
                    if client.is_visitor(myTimeEpoch, myTimeEpoch + timeIterator - 1) == True:
                        myVisitCount = myVisitCount + 1
                    
                    myTimeEpoch = myTimeEpoch + timeIterator
                                
                if myVisitCount >= round((loyaltyEndEpoch - loyaltyStartEpoch) / (timeIterator), 0) - 1:
                    dailyVisitors = dailyVisitors + 1
                elif myVisitCount >= round((loyaltyEndEpoch - loyaltyStartEpoch) / (timeIterator * 3), 0):
                    occasionalVisitors = occasionalVisitors + 1
                
                if client.is_visitor(loyaltyStartEpoch, currentTimeEpoch - 1) == False:
                    firstTimeVisitors = firstTimeVisitors + 1
        
        report = self.name + "," + currentDate + "," + str(occasionalVisitors) + "," + str(dailyVisitors) + "," + str(firstTimeVisitors)
        return report    
    
    # Method add_observation
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def add_observation(self, apMac, clientMac, ipv4, ipv6, seenTime, seenEpoch, ssid, rssi, manufacturer, os):
        newObservation = Observation(apMac, clientMac, ipv4, ipv6, seenTime, seenEpoch, ssid, rssi, manufacturer, os)
        myClient = self._find_client(clientMac)

        if myClient.clientMac == "":
            myClient.clientMac = clientMac
            myClient.manufacturer = manufacturer
            myClient.os = os
            self.clients.append(myClient)

        myClient.add_observation(newObservation)
        
        return None
        
    # Method discover_client_visits
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def discover_client_visits(self, observationsPerWindow, window, minStartRSSI, minSessionRSSI):
        for client in self.clients:
            client.discover_visits(observationsPerWindow, window, minStartRSSI, minSessionRSSI)
        
        return None
    
    # Method get_visits
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: None
    #####################################################################
    def get_visits(self):
        returnString = ""

        for client in self.clients:
            returnString = returnString + client.get_visits(self.name)
        
        return returnString

    # Method get_observations builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def get_observations(self):
        returnString = ""
        
        for client in self.clients:
            returnString = returnString + client.get_observations(self.name)

        return returnString


#########################################################################
# Class Visit
#
# 
#########################################################################
class Visit:
    # Method __init__ initializes the class variables
    #
    # Input: None
    # Output: None
    # Parameters: 
    #
    # Return Value: None
    #####################################################################
    def __init__(self, startTimeEpoch, endTimeEpoch):
        self.startTimeEpoch = startTimeEpoch
        self.endTimeEpoch = endTimeEpoch
        self.length = 0
        self.connected = False

    # Method to_string builds a CSV string of all class variables
    #
    # Input: None
    # Output: None
    # Parameters: None
    #
    # Return Value: CSV string of all class variables
    #####################################################################
    def to_string(self):
        returnString = epochtime_to_datetime(self.startTimeEpoch) + "," + epochtime_to_datetime(self.endTimeEpoch) + "," + str(self.length) + "," + str(self.connected)
        
        return returnString

# Method find_network 
#
# Input: None
# Output: None
# Parameters: None
#
# Return Value: -1 of error, index of first occurrence if found
#####################################################################
def find_network(networkName, networks):
    for network in networks:
        if network.name == networkName:
            return network
    
    newNetwork = Network(networkName)
    
    networks.append(newNetwork)

    return newNetwork

# Method find_first_day 
#
# Input: None
# Output: None
# Parameters: None
#
# Return Value: -1 of error, index of first occurrence if found
#####################################################################
def find_first_day(networks):
    # Declare variables
    startEpoch = 0
    year = ""
    month = ""
    day = ""

    for network in networks:
        for client in network.clients:
            for visit in client.visits:
                if (startEpoch == 0) or (startEpoch > visit.startTimeEpoch):
                    startEpoch = visit.startTimeEpoch

    year = long(epochtime_to_datetime(startEpoch,'%Y-%m-%d').split('-')[0])
    month = long(epochtime_to_datetime(startEpoch,'%Y-%m-%d').split('-')[1])
    day = long(epochtime_to_datetime(startEpoch,'%Y-%m-%d').split('-')[2])
    
    startEpoch = datetime_to_epochtime(year, month, day)
    
    return startEpoch

# Method find_last_day 
#
# Input: None
# Output: None
# Parameters: None
#
# Return Value: -1 of error, index of first occurrence if found
#####################################################################
def find_last_day(networks):
    # Declare variables
    endEpoch = 0
    year = ""
    month = ""
    day = ""

    for network in networks:
        for client in network.clients:
            for visit in client.visits:
                if endEpoch < visit.endTimeEpoch:
                    endEpoch = visit.endTimeEpoch

    year = long(epochtime_to_datetime(endEpoch,'%Y-%m-%d').split('-')[0])
    month = long(epochtime_to_datetime(endEpoch,'%Y-%m-%d').split('-')[1])
    day = long(epochtime_to_datetime(endEpoch,'%Y-%m-%d').split('-')[2])
    
    endEpoch = datetime_to_epochtime(year, month, day, 23, 59, 59)
    
    return endEpoch    

# Method epoch_to_date 
#
# Input: None
# Output: None
# Parameters: None
#
# Return Value: -1 of error, index of first occurrence if found
#####################################################################
def epochtime_to_datetime(epochTime, dateFormat='%Y-%m-%d %H:%M:%S'):
    return time.strftime(dateFormat, time.gmtime(epochTime))

# Method datetime_to_epochtime 
#
# Input: None
# Output: None
# Parameters: None
#
# Return Value: -1 of error, index of first occurrence if found
#####################################################################
def datetime_to_epochtime(year, month, day, hour=0, minute=0, second=0):
    return ((datetime.datetime(year, month, day, hour, minute, second) - datetime.datetime(1970,1,1)).total_seconds())



# Method main 
#
# Input: None
# Output: None
# Parameters: None
#
# Return Value: -1 of error, index of first occurrence if found
#####################################################################
def main():
    # Method variables
    outputHeader = "Network,AP Mac,Client Mac,ipv4 Address,ipv6 Address,Seen Time,Seen Epoch,SSID,RSSI,Manufacturer,Operating System"
    networks = []
    inputFile = ""
    fileOutput = ""
    csv_file_preamble = ""
    startTimeRangeEpoch = 0
    endTimeRangeEpoch = 0
    currentTime = 0
    
    # Check if all arguments exist and exit with info if failed
    if len(sys.argv) < 3:
        print ("meraki_cmx_analyze <input_file_name> <csv_file_preamble>")
        return None
    
    # Build input file and strip extra characters from preamble
    csv_file_preamble = sys.argv[2].strip()
    inputStream = open(sys.argv[1], 'r')
    allLines = [i for i in inputStream]
    
    # For each line add observations find the network it is associated with and add the observation to the correct network
    for line in allLines:
        if not ("Seen Epoch" in line) and ("," in line):
            networkName = line.split(',')[0].strip()
            apMac = line.split(',')[1].strip()
            clientMac = line.split(',')[2].strip()
            ipv4 = line.split(',')[3].strip()
            ipv6 = line.split(',')[4].strip()
            seenTime = line.split(',')[5].strip()
            seenEpoch = line.split(',')[6].strip()
            ssid = line.split(',')[7].strip()
            rssi = line.split(',')[8].strip()
            manufacturer = line.split(',')[9].strip()
            os = line.split(',')[10].strip()
            
            # Call find_network to identify the network for this new observation
            myNetwork = find_network(networkName, networks)
            
            # Add observation to the network
            myNetwork.add_observation(apMac, clientMac, ipv4, ipv6, seenTime, seenEpoch, ssid, rssi, manufacturer, os)

    # Print list of client observations
    print("---------------------------------------------------------------------------")
    print("Calculating Client Observations")
    print("---------------------------------------------------------------------------")
    fileOutput = "Network,AP Mac,Client Mac,ipv4,ipv6,Seen Time,Epoch Time,SSID,RSSI,Manufacturer,OS" + "\n"
    # For each network get list of client observations
    for network in networks:
        cmx_report_data = network.get_observations()
        fileOutput = fileOutput + cmx_report_data
    
    # Output list of client observations
    f = open(csv_file_preamble + "_client_observations.csv",'w')
    f.write(fileOutput)
    f.close()
        
    # Calculate client visits
    print("---------------------------------------------------------------------------")
    print("Calculating Client Visits")
    print("---------------------------------------------------------------------------")
    fileOutput = "Network,Client Mac,Seen Time Start,Seen Time End,Visit Length,Connected" + "\n"
    # Calculate client visits for each network
    for network in networks:
        # Calculate visit as 5 observations per window, 1200 second window, min start RSSI 20, min session RSSI 15
        network.discover_client_visits(5,1200,20,15)
        # Gather visits and print
        cmx_report_data = network.get_visits()
        fileOutput = fileOutput + cmx_report_data
    
    # Output visits to file
    f = open(csv_file_preamble + "_client_visits.csv",'w')
    f.write(fileOutput)
    f.close()
    
    # Search all networks for the first and last calendar day in file
    startTimeRangeEpoch = find_first_day(networks)
    endTimeRangeEpoch = find_last_day(networks)
    
    # Set currentTime to first day
    currentTime = startTimeRangeEpoch
    
    # Print proximity report
    print("---------------------------------------------------------------------------")
    print("Calculating CMX Proximity Report")
    print("---------------------------------------------------------------------------")
    fileOutput = "Network,Date,Passerby,Visitors,Connected,Capture Rate" + "\n"
    # While we have not reached the last day, gather the proximity report for each day
    while currentTime < endTimeRangeEpoch:
        for network in networks:
            cmx_report_data = network.get_cmx_proximity_report(currentTime, currentTime + 86399)
            fileOutput = fileOutput + cmx_report_data + "\n"
        
        currentTime = currentTime + 86400
    
    # Write report to output file
    f = open(csv_file_preamble + "_cmx_proximity_report.csv",'w')
    f.write(fileOutput)
    f.close()
    
    # Set currentTime to first day
    currentTime = startTimeRangeEpoch
    
    print("---------------------------------------------------------------------------")
    print("Calculating CMX Engagement Report")
    print("---------------------------------------------------------------------------")
    fileOutput = "Network,Date,5-20 mins,20-60 mins,1-6 hrs,6+ hrs" + "\n"
    while currentTime < endTimeRangeEpoch:
        for network in networks:
            cmx_report_data = network.get_cmx_engagement_report(currentTime, currentTime + 86399)
            fileOutput = fileOutput + cmx_report_data + "\n"
        
        currentTime = currentTime + 86400

    # Write report to output file
    f = open(csv_file_preamble + "_cmx_engagement_report.csv",'w')
    f.write(cmx_report_data)
    f.close()

    # Set currentTime to first day
    currentTime = startTimeRangeEpoch

    print("---------------------------------------------------------------------------")
    print("Calculating CMX Loyalty Report")
    print("---------------------------------------------------------------------------")
    fileOutput = "Network,Date,Occasional,Daily,First Time" + "\n"
    while currentTime < endTimeRangeEpoch:
        for network in networks:
            cmx_report_data = network.get_cmx_loyalty_report(currentTime, startTimeRangeEpoch, endTimeRangeEpoch, 86400)
            fileOutput = fileOutput + cmx_report_data + "\n"
        
        currentTime = currentTime + 86400
    
    f = open(csv_file_preamble + "_cmx_loyalty_report.csv",'w')
    f.write(cmx_report_data)
    f.close()
    
    return None
    
    
if __name__ == '__main__':
    try:
        main()
    except Exception, e:
        print str(e)
        os._exit(1)
