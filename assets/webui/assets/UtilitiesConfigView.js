import{C as h}from"./ConfigurationList.js";import{d as v,r as n,o as m,c as y,a as u,f as l,u as x,S as k,_ as w}from"./index.js";import{u as C,a as b}from"./use-message.js";import"./cryptojs.js";const V={class:"sub-content-wrapper"},S={class:"sidebar-wrapper"},B={class:"sub-main-content-wrapper"},j=v({__name:"UtilitiesConfigView",setup(z){x();const p=[{key:"trigger",text:"触发设置",path:"/utilites/trigger"},{key:"response",text:"回复设置",path:"/utilites/response"},{key:"text_to_image",text:"文字转图片",path:"/utilites/text_to_image"},{key:"text_to_speech",text:"文字转语音",path:"/utilites/text_to_speech"},{key:"azure",text:"Azure 语音引擎设置",path:"/utilites/azure"},{key:"vits",text:"VITS 语音引擎设置",path:"/utilites/vits"},{key:"baiducloud",text:"百度云审核",path:"/utilites/baiducloud"},{key:"ratelimit",text:"额度限制",path:"/utilites/ratelimit"},{key:"system",text:"其他功能设置",path:"/utilites/system"}],a=C(),i=b(),o=n("onebot"),r=n([]),c=n({});async function f(){const t=await(await fetch("/backend-api/v1/config?key="+o.value+"&type=schema")).json();r.value=[t]}async function _(){const t=await(await fetch("/backend-api/v1/config?key="+o.value+"&type=value")).json();c.value=t}function g(e){o.value=e,s()}function s(){a.start(),f().then(()=>_()).then(()=>{a.finish()}).catch(e=>{i.error("配置读取失败："+e),a.error()})}function d(e){a.start(),console.log(e),fetch("/backend-api/v1/config?key="+o.value,{method:"POST",body:JSON.stringify(e),headers:{Accept:"application/json","Content-Type":"application/json"}}).then(t=>{if(t.ok)return i.success("配置已保存"),a.finish(),t.text();throw new Error(t.text())}).catch(t=>{i.error("配置保存失败："+t),a.error()})}return s(),(e,t)=>(m(),y("div",V,[u("div",S,[l(k,{"nav-list":p,onOnSelect:g,"icon-only":!1,title:"功能设置"})]),u("div",B,[l(h,{title:o.value,"configuration-groups":r.value,configurationValue:c.value,onSave:d,onReset:s},null,8,["title","configuration-groups","configurationValue"])])]))}});const T=w(j,[["__scopeId","data-v-10256533"]]);export{T as default};
