# Api Overview

#### List of Primitives

* Generates a Task_ID based on a user request expressed in natural language (NL). 
```
generateTask(NL, {parameters}) → Task_ID
```

* Generates an AP in JSON format to accomplish the given Task_ID. 
```
generateAP(Task_ID) → AP: PG JSON
```

* Stores an AP in JSON format in the AP management database and returns its AP_ID. 
```
storeAP(AP: JSON) → AP_ID 
```

* Retrieves the APs associated with the given Task_ID. 
```
retrieveAP(Task_ID) → {AP_ID}  
```

* Executes the AP identified by AP_ID and returns the execution results. 
```
executeAP(AP_ID) → ExecutionResult
```

* Compares two APs associated with the same Task_ID and returns a JSON comparison result. 
```
compareAP(Task_ID, AP1_ID, AP2_ID) → ComparisonResult: JSON
```

* Combines multiple APs into a single AP (returned in JSON format).  
```
composeAP({AP_ID}) → AP: PG JSON
```

* Provides an explanation of an AP based on its execution result and returns explainability information.   
```
explainAP(AP: JSON, result: ExecutionResult) → ExplanationResult 
```

* Displays the structure of the input AP and its operators. 
```
displayAP(AP: JSON) → RenderedView
```

* Selects the appropriate Task_ID from an existing list of tasks, given an NL description. 
```
getTask(NL, {parameters}, {Tasks}) → Task_ID 
```

* Evaluates an AP along three dimensions: data, system, and human. Returns a JSON-formatted evaluation result.  
```
evaluateAP(AP: JSON) → EvaluationResult: JSON 
```
 
