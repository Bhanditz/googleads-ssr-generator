# Snippt Status Report Generator #

A Python program to generate Snippet Status Reports in txt, protocol buffer, and
csv format.

## Setup ##

* Install the [Python Protocol Buffers library](http://code.google.com/p/protobuf/).

* Download and install the **Google API Python Client** with either
   easy_install or pip:

  * Using easy_install:

      ```
      $ easy_install --upgrade google-api-python-client
      ```

  * Using pip:

      ```
      $ pip install --upgrade google-api-python-client
      ```
* If you haven't done so already, contact your Google Technical Account
  Manager to set up a
  [Service Account](https://developers.google.com/accounts/docs/OAuth2ServiceAccount)
  to use with the DoubleClick Ad Exchange Buyer REST API.

* In order to make calls to the Google Ad-Exchange Buyer API, you will need to
  use the OAuth 2.0 protocol for authentication and authorization. You need to
  create a client_secrets.json file and put it inside this directory. To obtain
  the JSON file, go to the
  [Google Developers Console](https://console.developers.google.com/),
  click your project, and click the `APIs & auth` and then the `Credentials`
  tab and find the Service Account, and click `Download JSON`

  For more information on using OAuth 2.0, visit
  https://developers.google.com/accounts/docs/OAuth2

  For general information on calling Google APIs using Python, please visit
  https://developers.google.com/api-client-library/python/


## Running the Application ##
Before running this application you must generate the Python file for the
snippet-status-report.proto protocol buffer. You only need to do this once. Run
the command:

  ```
  make
  ```

To generate Snippet Status Reports, run the following command:

  ```
  python generate_ssr.py
  ```

The program will generate three files:

* SnippetStatusReport.txt

* SnippetStatusReport.pb

* SnippetStatusReport.csv

You can open the csv file using a spreadsheet program such as Microsoft Excel,
or LibreOffice Calc

## Notes ##
The included protocol buffer file is the latest at the time of publishing. If
you would like to use this application against another version of
snippet-status-report.proto, either copy the file into this directory or set the
PROTO_SRC_DIR variable in the Makefile to the directory containing
snippet-status-report.proto.
