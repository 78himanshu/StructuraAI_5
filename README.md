# StructuraAI

AI-powered extraction and structuring of financial document metadata from large-scale I/B/E/S historical earnings documentation.

## Overview

StructuraAI is a document intelligence pipeline designed to transform large, unstructured financial documentation into machine-readable structured data. The project automates the extraction of file layouts, field definitions, metadata, and schema information from extensive I/B/E/S (Institutional Brokers' Estimate System) documentation and converts them into standardized JSON structures suitable for downstream analytics and data engineering workflows.

The system leverages Large Language Models (LLMs) to interpret complex financial documentation and generate structured outputs that can be integrated into automated data processing pipelines.

## Problem Statement

Financial data providers often distribute documentation as lengthy PDF manuals containing hundreds of pages of field definitions, file layouts, and metadata specifications. Manually extracting and maintaining these schemas is time-consuming, error-prone, and difficult to scale.

StructuraAI automates this process by:

- Parsing large financial documentation files
- Identifying structured metadata definitions
- Extracting field-level schema information
- Generating machine-readable JSON outputs
- Reducing manual documentation processing effort

## Features

- Automated PDF documentation processing
- Financial schema extraction and normalization
- Structured JSON generation
- Metadata parsing and validation
- Support for large-scale financial documentation
- LLM-assisted field interpretation
- Reusable extraction framework for future document sets

## Technology Stack

### Languages
- Python

### Libraries & Tools
- OpenAI API
- JSON Schema
- Regular Expressions (Regex)
- PDF Processing Utilities

### Data Sources
- I/B/E/S Summary History Documentation
- I/B/E/S Detail History Documentation

## Project Architecture

text Financial Documentation PDFs             │             ▼       PDF Processing             │             ▼     Metadata Extraction             │             ▼       Schema Detection             │             ▼     Structured JSON Output             │             ▼  Downstream Analytics Systems 


## Example Output

The extracted output follows a standardized JSON schema format:

json {   "file_name": "example_file",   "key": "A#1",   "item": "Ticker",   "data_type": "string",   "format": "CCCCCC",   "length": 6,   "start": 1,   "end": 6,   "comments": "Primary identifier" } 

## Installation

Clone the repository:

bash git clone https://github.com/yourusername/StructuraAI.git cd StructuraAI 

Create a virtual environment:

bash python -m venv .venv source .venv/bin/activate 

Install dependencies:

bash pip install -r requirements.txt 

## Usage

1. Place the financial documentation PDFs in the project directory.
2. Configure your API credentials.
3. Run the extraction pipeline:

bash python schema_extractor.py 

4. Review the generated structured JSON output.

## Applications

- Financial Data Engineering
- Metadata Management
- Data Catalog Generation
- Schema Discovery
- Documentation Automation
- Data Governance
- ETL Pipeline Development

## Future Enhancements

- Multi-document ingestion support
- Automated schema validation
- Database schema generation
- Knowledge graph integration
- Data lineage generation
- Interactive schema explorer

## Author

Himanshu 

Master of Science in Computer Science  
Stevens Institute of Technology
