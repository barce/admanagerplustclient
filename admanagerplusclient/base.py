#!/usr/bin/env python

import json
import requests
import base64

import sys

# if sys.version_info < (3, 0):
#     raise "must use python 2.5 or greater"

use_environment_variables = None

try:
    from django.conf import settings
except ImportError:
    use_environment_variables = True


class Base:
    client_id = None
    client_secret = None
    id_host = None
    dsp_host = None
    request_auth_url = None
    yahoo_auth = None
    raw_token_results = None
    refresh_token = None
    token = None
    current_url = ''
    report_url = ''
    customerReportId = ''
    report_results_url = ''
    headers = None
    curl_url = None
    curl_command = None
    payload = ''

    def __init__(self, client_id, client_secret, refresh_token):

        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.id_host = "https://api.login.yahoo.com"
        self.dsp_host = "https://dspapi.admanagerplus.yahoo.com"

        self.request_auth_url = self.id_host + "/oauth2/request_auth?client_id=" + self.client_id + "&redirect_uri=oob&response_type=code&language=en-us"
        self.current_url = ''
        self.report_url = 'https://api-sched-v3.admanagerplus.yahoo.com/yamplus_api/extreport/'

        try:
            self.raw_token_results = {}
            self.raw_token_results['refresh_token'] = self.refresh_token
        except KeyError as e:
            print("error missing:")
            print(e)

        self.inventory_payload = None

    def set_refresh_token(self, refresh_token):
        self.refresh_token = refresh_token
        self.raw_token_results = {}
        self.raw_token_results['refresh_token'] = refresh_token
        return self.refresh_token

    def get_yahoo_auth_url(self):
        print("Go to this URL:")
        print(self.request_auth_url)

    def set_yahoo_auth(self, s_auth):
        self.yahoo_auth = s_auth
        return self.yahoo_auth

    def base64auth(self):
        return base64.b64encode((self.client_id + ":" + self.client_secret).encode())

    def get_access_token_json(self):
        get_token_url = self.id_host + "/oauth2/get_token"
        # payload = {'grant_type':'authorization_code', 'redirect_uri':'oob','code':self.yahoo_auth}
        payload = "grant_type=authorization_code&redirect_uri=oob&code=" + self.yahoo_auth
        # headers = {'Content-Type': 'application/json', 'Authorization': "Basic " + self.base64auth()}
        headers = {'Content-Type': 'application/x-www-form-urlencoded',
                   'Authorization': "Basic " + self.base64auth().decode('utf-8')}

        print(get_token_url)
        print(payload)
        print(headers)

        r = requests.post(get_token_url, data=payload, headers=headers)
        results_json = r.json()
        return results_json

    def refresh_access_token(self):
        get_token_url = self.id_host + "/oauth2/get_token"
        # try to UTF-8 encode refresh token
        try:
            payload = "grant_type=refresh_token&redirect_uri=oob&refresh_token=" + self.raw_token_results[
                'refresh_token'].encode('utf-8')
        except:
            payload = "grant_type=refresh_token&redirect_uri=oob&refresh_token=" + self.raw_token_results[
                'refresh_token']

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': "Basic " + self.base64auth().decode('utf-8')
        }
        r = requests.post(get_token_url, data=payload, headers=headers)
        results_json = r.json()
        try:
            self.token = results_json['access_token']
        except:
            pass
        # self.raw_token_results = r.json()
        # self.refresh_token = self.raw_token_results['refresh_token']
        return results_json

    def cli_auth_dance(self): 
        self.get_yahoo_auth_url()
        if sys.version_info < (3, 0):
            self.yahoo_auth = raw_input("Enter Yahoo! auth code: ")
        else:
            self.yahoo_auth = input("Enter Yahoo! auth code: ")

        print("Auth code, {}, entered.".format(self.yahoo_auth))
        self.raw_token_results = self.get_access_token_json()
        print("raw_token_results:")
        print(self.raw_token_results)
        self.refresh_token = self.raw_token_results['refresh_token']
        print("refresh_token:")
        print(self.refresh_token)

    #
    #
    # traffic types
    #
    #

    def generate_json_response(self, r, results_json, request_body):
        response_json = {
            'request_body': self.curl_command
        }

        if results_json['errors'] is not None:
            response_json['msg_type'] = 'error'
            response_json['msg'] = results_json['errors']
            response_json['data'] = results_json['errors']
            response_json['response_code'] = results_json['errors']['httpStatusCode']

        else:
            response_json['msg_type'] = 'success'
            # display the error message that comes back from request
            response_json['msg'] = ''
            response_json['data'] = results_json
            response_json['response_code'] = r.status_code

        return response_json

        # make_request(method_type) --> pass in method_type

    def make_request(self, url, headers, method_type, data=None):
        request_body = url, headers, data
        r, results_json = self.make_new_request(url, self.token, method_type, headers, data)

        if results_json['errors'] is not None:
            if results_json['errors']['httpStatusCode'] in [400, 401]:
                # refresh access token
                self.token = self.refresh_access_token()['access_token']
                # apply headers with new token, return response and response dict
                r, results_json = self.make_new_request(url, self.token, method_type, headers, data)

        # use results_json to create updated json dict
        response_json = self.generate_json_response(r, results_json, request_body)

        return json.dumps(response_json)

    def make_new_request(self, url, token, method_type, headers, data=None):
        #print ("URL")
        #print (url)
        #print ("DATA")
        #print (data)

        # modify headers with new access token
        headers['X-Auth-Token'] = token
        if method_type == 'GET':
            r = requests.get(url, headers=headers)
        if method_type == 'POST':
            r = requests.post(url, headers=headers, verify=False, data=json.dumps(data))
        if method_type == 'PUT':
            r = requests.put(url, headers=headers, verify=False, data=json.dumps(data))
        results_json = r.json()

        #print ("results_json")
        #print (results_json)
        command = "curl -v -H {headers} {data} -X {method} {uri}"
        header_list = ['"{0}: {1}"'.format(k, v) for k, v in headers.items()]
        header = " -H ".join(header_list)
        self.curl_command = command.format(method=method_type, headers=header, data=data, uri=url)
        """
        print ("===========================")
        print ("")
        print (command.format(method=method_type, headers=header, data=data, uri=url))
        print ("")
        print ("")
        print ("================================")
        """

        return r, results_json

    def traffic_types(self, s_type, seat_id=None):
        headers = {'Content-Type': 'application/json', 'X-Auth-Method': 'OAUTH', 'X-Auth-Token': str(self.token)}
        url = self.dsp_host + "/traffic/" + str(s_type)
        if seat_id is not None:
            url += "/?seatId=" + str(seat_id)

        r = self.make_request(url, headers, 'GET')
        return r

    # Works for s_types:
    # advertisers, campaigns, lines
    def traffic_type_by_id(self, s_type, cid, seat_id):
        headers = {'Content-Type': 'application/json', 'X-Auth-Method': 'OAUTH', 'X-Auth-Token': str(self.token)}
        self.headers = headers
        url = self.dsp_host + "/traffic/" + str(s_type)
        url = url + "/" + str(cid) + "/?seatId=" + str(seat_id)
        # self.curl_url = url
        # self.debug_curl()

        r = self.make_request(url, headers, 'GET')
        return r

    # TODO:
    # do not pass to the results string if not set on our end
    def traffic_types_by_filter(self, s_type, account_id, page=0, limit=0, sort='', direction='asc', query=''):
        headers = {'Content-Type': 'application/json', 'X-Auth-Method': 'OAUTH', 'X-Auth-Token': str(self.token)}
        url = self.dsp_host + "/traffic/" + str(s_type)
        if s_type == 'lines':
            url = url + "?orderId=" + str(account_id)
        else:
            url = url + "?accountId=" + str(account_id)

        if page > 0:
            url = url + "&page=" + str(page)
        if limit > 0:
            url = url + "&limit=" + str(limit)
        if sort != '':
            url = url + "&sort=" + str(sort)
        if query != '':
            url = url + "&query=" + str(query)
        url = url + "&dir=" + str(direction)

        r = self.make_request(url, headers, 'GET')
        r = json.loads(r)
        r['data']['response'] = r['data']['response'][0]
        r = json.dumps(r)
        return r

    def update_traffic_type(self, s_type, cid, payload, seat_id):
        headers = {'Content-Type': 'application/json', 'X-Auth-Method': 'OAUTH', 'X-Auth-Token': str(self.token)}
        url = self.dsp_host + "/traffic/" + str(s_type) + "/" + str(cid) + "/?seatId=" + str(seat_id)
        r = self.make_request(url, headers, 'PUT', payload)
        return r

    def create_traffic_type(self, s_type, payload, seat_id):
        headers = {'Content-Type': 'application/json', 'X-Auth-Method': 'OAUTH', 'X-Auth-Token': str(self.token)}
        url = self.dsp_host + "/traffic/" + str(s_type) + "/?seatId=" + str(seat_id)
        r = self.make_request(url, headers, 'POST', payload)
        return r
