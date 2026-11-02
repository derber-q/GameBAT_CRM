const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');

function runtime(){
  let listener,calls=0,lastData,url='/crm/sales/avito-orders/1/create/';
  const tab={id:1,url:'http://127.0.0.1:8000/crm/sales/avito-extension/'};
  const chrome={runtime:{id:'test-extension',onMessage:{addListener(fn){listener=fn;}}},
    storage:{session:{async get(){return{};},async set(){}}},tabs:{
      async query(){calls++;return[tab];},async get(){return tab;},
      async sendMessage(id,message){if(message.data)lastData=message.data;return {ok:true,orders:{},url};},
      async create(){calls++;return tab;}
    }};
  const context=vm.createContext({chrome,URL,console,setTimeout,crypto:globalThis.crypto});
  for(const file of ['protocol.js','orders-background.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,file),'utf8'),context);
  const sender={id:chrome.runtime.id,frameId:0,tab:{id:2},url:'https://www.avito.ru/orders'};
  const send=(message,from=sender)=>new Promise(resolve=>assert.equal(listener({type:'resource-orders:action',...message},from,resolve),true));
  return {sender,send,get calls(){return calls;},get lastData(){return lastData;},setURL(value){url=value;}};
}

// Страница отдаёт код только при полноценном мобильном окружении, а не UA-заголовке.
function printingRuntime({existing=false,failEmulation=false,kind='128',failCapture=false,invalidClip=false}={}){
  let listener,created=0,detached=0,removed=0,fetches=0,printData;
  const commands=[];
  const crm={id:1,url:'http://127.0.0.1:8000/crm/sales/avito-extension/'};
  const mobile={id:3,url:'about:blank'};
  const id='70000000000000001';
  const label={source:'https://avito.ru/web/1/barcode/generate?barcodeType='+kind+'&content=00123456789012',carrier:kind==='128'?'Почта России':'5Post'};
  const chrome={runtime:{id:'test-extension',onMessage:{addListener(fn){listener=fn;}}},
    storage:{session:{async get(){return{};},async set(){}}},
    debugger:{async attach(target){assert.equal(target.tabId,3);},
      async sendCommand(target,method,params){
        assert.equal(target.tabId,3);commands.push({method,params});
        if(failEmulation)throw new Error('Mobile emulation unavailable');
        if(method==='Page.captureScreenshot'){
          if(failCapture)throw new Error('Capture failed');
          assert.equal(params.clip.width,200);assert.equal(params.clip.height,200);
          return {data:'original-rendered-png'};
        }
      },async detach(target){assert.equal(target.tabId,3);detached++;}},
    tabs:{async query(){return existing?[crm,{id:4,url:'https://m.avito.ru/orders/'+id}]:[crm];},
      async create(){created++;return mobile;},async update(tabId,{url}){mobile.url=url;return mobile;},
      async get(tabId){return tabId===1?crm:mobile;},async remove(tabId){assert.equal(tabId,3);removed++;},
      async sendMessage(tabId,message){
        if(message.type==='resource-orders:label'){
          const ready=existing || commands.some(c=>c.method==='Emulation.setDeviceMetricsOverride'&&c.params.mobile&&c.params.width<=430) &&
            commands.some(c=>c.method==='Emulation.setUserAgentOverride'&&c.params.userAgentMetadata.mobile) &&
            commands.some(c=>c.method==='Emulation.setTouchEmulationEnabled'&&c.params.enabled);
          return {ok:true,label:ready?label:null};
        }
        if(message.type==='resource-orders:label_capture')return {ok:true,label,clip:{x:0,y:100,width:invalidClip?5000:200,height:200,scale:1}};
        printData=message.data;return {ok:true,job_id:5};
      }}};
  const context=vm.createContext({chrome,URL,console,AbortSignal,crypto:globalThis.crypto,
    fetch(){fetches++;throw new TypeError('Failed to fetch');},setTimeout(fn){queueMicrotask(fn);}});
  for(const file of ['protocol.js','orders-background.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,file),'utf8'),context);
  return {run:()=>new Promise(resolve=>listener({type:'resource-orders:action',action:'print',order:{order_id:id}},
    {id:chrome.runtime.id,frameId:0,tab:{id:2},url:'https://www.avito.ru/orders'},resolve)),
    get state(){return {created,detached,removed,fetches,printData};}};
}

function reconnectRuntime({login=false,concurrent=false}={}){
  let listener,live=false,reloads=0,requests=0;
  const tab={id:1,status:'complete',url:'http://127.0.0.1:8000/crm/sales/'+(login?'../accounts/login/':'avito-extension/')};
  if(login)tab.url='http://127.0.0.1:8000/crm/accounts/login/?next=/crm/sales/avito-extension/';
  const chrome={runtime:{id:'test-extension',onMessage:{addListener(fn){listener=fn;}}},
    storage:{session:{async get(){return {'resource-orders:connection':{id:1,origin:'http://127.0.0.1:8000'}};},async set(){}}},
    tabs:{async query(){return[tab];},async get(){return tab;},
      async reload(){reloads++;live=true;},
      async sendMessage(id,message){
        if(!live)throw new Error('Could not establish connection. Receiving end does not exist.');
        if(message.type==='resource-orders:ping')return {ok:true};
        requests++;return {ok:true,orders:{'70000000000000001':{sale_number:'SALE-000398',sale_url:'/crm/sales/398/'}}};
      }}};
  const context=vm.createContext({chrome,URL,console,crypto:globalThis.crypto,setTimeout(fn){queueMicrotask(fn);}});
  for(const file of ['protocol.js','orders-background.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,file),'utf8'),context);
  const run=()=>new Promise(resolve=>listener({type:'resource-orders:action',action:'lookup',ids:['70000000000000001']},
    {id:chrome.runtime.id,frameId:0,tab:{id:2},url:'https://www.avito.ru/orders'},resolve));
  return {run:()=>concurrent?Promise.all([run(),run()]):run(),get state(){return {reloads,requests};}};
}
(async()=>{
  const app=runtime();
  for(const sender of [{...app.sender,id:'other'},{...app.sender,frameId:1},{...app.sender,url:'https://evil.example/orders'}])
    assert.equal((await app.send({action:'lookup',ids:[]},sender)).ok,false);
  assert.equal(app.calls,0);
  assert.equal((await app.send({action:'draft',order:{order_id:70000000000000001}})).ok,false);
  assert.equal(app.calls,0);
  assert.equal((await app.send({action:'lookup',ids:['70000000000000001']})).origin,'http://127.0.0.1:8000');
  assert.equal((await app.send({action:'sale_status',order_id:70000000000000001})).ok,false);
  assert.equal((await app.send({action:'sale_status',order_id:'70000000000000001',field:'order',value:'assembled',version:'v1',confirmed:true})).ok,true);
  assert.equal(app.lastData.field,'order');assert.equal(app.lastData.value,'assembled');
  assert.equal((await app.send({action:'cancel_sale',order_id:'70000000000000001',version:'v1',comment:'Test',confirmed:true,sale_id:999})).ok,true);
  assert.equal(app.lastData.comment,'Test');assert.equal(app.lastData.sale_id,undefined);
  app.setURL('https://evil.example/');
  assert.equal((await app.send({action:'draft',order:{order_id:'70000000000000001'}})).ok,false);
  const printing=printingRuntime();assert.equal((await printing.run()).ok,true);
  assert.equal(printing.state.printData.symbol.content,'00123456789012');
  assert.equal(printing.state.detached,1);assert.equal(printing.state.removed,1);
  const failed=printingRuntime({failEmulation:true});assert.equal((await failed.run()).ok,false);
  assert.equal(failed.state.detached,1);assert.equal(failed.state.removed,1);assert.equal(failed.state.printData,undefined);
  const opened=printingRuntime({existing:true});assert.equal((await opened.run()).ok,true);
  assert.equal(opened.state.created,0);assert.equal(opened.state.detached,0);assert.equal(opened.state.removed,0);
  assert.equal(opened.state.printData.symbol.content,'00123456789012');
  for(const kind of ['QR','QR_CODE','QrCode','qrcode']){
    const local=printingRuntime({existing:true,kind});assert.equal((await local.run()).ok,true);
    assert.equal(local.state.printData.symbol.type,'QR');
    assert.equal(local.state.printData.symbol.content,'00123456789012');
    assert.equal(local.state.fetches,0);assert.equal(local.state.created,0);
  }
  const qr=printingRuntime({existing:true,kind:'QR_IMAGE'});assert.equal((await qr.run()).ok,true);
  assert.equal(qr.state.printData.image,'original-rendered-png');assert.equal(qr.state.printData.order.carrier,'5Post');
  assert.equal(qr.state.fetches,0);assert.equal(qr.state.created,1);assert.equal(qr.state.detached,1);assert.equal(qr.state.removed,1);
  for(const options of [{kind:'QR_IMAGE',failCapture:true},{kind:'QR_IMAGE',invalidClip:true}]){
    const broken=printingRuntime(options);assert.equal((await broken.run()).ok,false);
    assert.equal(broken.state.printData,undefined);assert.equal(broken.state.detached,1);assert.equal(broken.state.removed,1);
  }
  const stale=reconnectRuntime({concurrent:true});
  const restored=await stale.run();assert.equal(restored[0].ok,true);assert.equal(restored[1].ok,true);
  assert.equal(restored[0].orders['70000000000000001'].sale_number,'SALE-000398');
  assert.equal(stale.state.reloads,1);assert.equal(stale.state.requests,2);
  const login=reconnectRuntime({login:true});assert.equal((await login.run()).ok,false);
  assert.equal(login.state.reloads,0);assert.equal(login.state.requests,0);
  console.log('Avito orders: sender/frame/origin guards, string IDs and CRM URL validation OK');
})().catch(error=>{console.error(error);process.exitCode=1;});
