// 模拟 API 返回的数据
const wfData = {
  "id": "b9eeadc5-233f-420e-a238-723564077fac",
  "nodes": [
    {
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
    }
  ]
};

// 模拟前端 store
const nodes = wfData.nodes;

// 模拟 startNode computed
const startNode = nodes.find(n => n.type === 'start');
console.log('startNode:', startNode);

// 模拟 hasStartInputVariables computed
const inputVars = startNode?.data?.config?.input_variables;
console.log('inputVars:', inputVars);
console.log('hasStartInputVariables:', inputVars && inputVars.length > 0);

// 模拟用户输入
const startInputValues = {};
inputVars.forEach(v => {
  startInputValues[v.name] = v.default !== undefined ? v.default : '';
});
console.log('startInputValues (initial):', startInputValues);

// 模拟用户填写
startInputValues['query'] = '这是用户输入的问题';
console.log('startInputValues (after user input):', startInputValues);
