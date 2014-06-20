PROTO_COMPILER=/usr/bin/protoc
SRC_DIR = .
PROTO_SRC_DIR = .
DEST_DIR = .

all: snippet_status_report_pb2.py

snippet_status_report_pb2.py: snippet-status-report.proto
	$(PROTO_COMPILER) -I=$(SRC_DIR) --python_out=$(DEST_DIR) snippet-status-report.proto

test: snippet_status_report_pb2.py
	python generate_ssr_test.py
