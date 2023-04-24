FROM fuzzers/atheris:2.0.7-python3.9

# Build
RUN pip install pybase64

# Add fuzzing script
ADD fuzz_pybase64.py /fuzz_pybase64.py

CMD ["/fuzz_pybase64.py"]
