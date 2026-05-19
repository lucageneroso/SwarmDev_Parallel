# SwarmDev Generated Documentation

> This documentation was generated as a fallback because the CodeWiki node encountered an error.

## Backend Code
```python
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
```

## Frontend Code
```javascript
const calculate = async (a, b, operation) => {
    try {
        const response = await fetch('/api/calculate', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ a, b, operation }),
        });

        if (!response.ok) {
            throw new Error('Network response was not ok');
        }

        const data = await response.json();
        return data.result;
    } catch (error) {
        console.error('Error:', error);
        throw error;
    }
};

export default calculate;
```
