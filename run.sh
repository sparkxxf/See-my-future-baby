if pgrep -f "main:app" > /dev/null ; then
    pkill -f "main:app"
fi

nohup uvicorn main:app --host 0.0.0.0 --port 8000  >> demo.log 2>&1 &