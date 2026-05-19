from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class CalculationRequest(BaseModel):
    num1: float
    num2: float
    operation: str

@app.post("/calculate")
async def calculate(request: CalculationRequest):
    if request.operation == "add":
        result = request.num1 + request.num2
    elif request.operation == "subtract":
        result = request.num1 - request.num2
    else:
        return {"error": "Invalid operation"}
    
    return {"result": result}