// 模拟前端数据
const node = {
  "id": "start-1",
  "data": {
    "rows": [
      ["测试测试", "1"]
    ],
    "config": {
      "input_variables": [
        {
          "name": "query",
          "source": "string"
        }
      ]
    }
  },
  "name": "Start",
  "type": "start",
  "position": {
    "x": 100,
    "y": 100
  }
};

const inputVars = node.data?.config?.input_variables;
console.log('inputVars:', inputVars);
console.log('length:', inputVars?.length);
console.log('hasStartInputVariables:', inputVars && inputVars.length > 0);
