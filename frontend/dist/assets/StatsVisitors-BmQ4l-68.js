import{d as h,j as _,y,k as w,o as S,c as u,a as t,l as m,v as f,f as l,z as g,F as k,r as C,A,t as T,h as p}from"./index-CEe5TGL3.js";const V={class:"space-y-4"},j={class:"flex items-center justify-between"},z={class:"flex gap-2 text-sm"},B={class:"grid sm:grid-cols-2 lg:grid-cols-4 gap-3"},K={class:"grid lg:grid-cols-2 gap-4"},D={class:"rounded-xl border p-4"},L={class:"grid grid-cols-12 gap-1 text-center text-xs"},M=["title"],N={components:{KpiCard:{props:{label:String,value:[String,Number]},template:'<div class="border rounded-xl p-4"><div class="text-xs opacity-60">{{label}}</div><div class="text-2xl">{{value}}</div></div>'},StatTable:{props:{title:String,rows:Array,cols:Array},template:`
      <div class="rounded-xl border overflow-hidden">
        <div class="p-3 font-medium border-b">{{ title }}</div>
        <table class="w-full text-sm">
          <thead class="bg-black/5 dark:bg-white/5">
            <tr><th v-for="c in cols" :key="c" class="p-2 text-left capitalize">{{ c }}</th></tr>
          </thead>
          <tbody>
            <tr v-for="(r,i) in rows" :key="i" class="border-t">
              <td v-for="c in cols" :key="c" class="p-2 truncate max-w-[0]">
                <a v-if="c==='url'" :href="r[c]" class="text-blue-600 underline" target="_blank">{{ r[c] }}</a>
                <span v-else>{{ r[c] ?? '—' }}</span>
              </td>
            </tr>
            <tr v-if="!rows || !rows.length"><td :colspan="cols.length" class="p-4 text-center opacity-60">Keine Daten</td></tr>
          </tbody>
        </table>
      </div>`}}},R=h({...N,__name:"StatsVisitors",setup(U){const r=_(""),i=_(""),e=y({total_visitors:0,chats_started:0,avg_wait_sec:0,cobrowse:0,top_pages:[],top_referrers:[],by_hour:Array(24).fill(0)}),x=w(()=>Math.max(1,...e.by_hour));function d(a){return typeof a=="number"?a.toLocaleString():"—"}async function v(){const a=new URLSearchParams;r.value&&a.set("from",r.value),i.value&&a.set("to",i.value);const s=await fetch(`/mock/stats/visitors.json?${a.toString()}`);Object.assign(e,await s.json())}return S(v),(a,s)=>{const n=g("KpiCard"),b=g("StatTable");return p(),u("div",V,[t("div",j,[s[2]||(s[2]=t("h1",{class:"text-xl font-semibold"},"Visitors Stats",-1)),t("div",z,[m(t("input",{type:"date","onUpdate:modelValue":s[0]||(s[0]=o=>r.value=o),class:"border rounded px-2 py-1"},null,512),[[f,r.value]]),m(t("input",{type:"date","onUpdate:modelValue":s[1]||(s[1]=o=>i.value=o),class:"border rounded px-2 py-1"},null,512),[[f,i.value]]),t("button",{class:"px-3 py-1.5 border rounded",onClick:v},"Aktualisieren")])]),t("div",B,[l(n,{label:"Besucher gesamt",value:d(e.total_visitors)},null,8,["value"]),l(n,{label:"Chats gestartet",value:d(e.chats_started)},null,8,["value"]),l(n,{label:"Avg. Wartezeit",value:e.avg_wait_sec?e.avg_wait_sec+"s":"—"},null,8,["value"]),l(n,{label:"Co-browse Sessions",value:d(e.cobrowse)},null,8,["value"])]),t("div",K,[l(b,{title:"Top-Seiten",rows:e.top_pages,cols:["url","views","chats"]},null,8,["rows"]),l(b,{title:"Top-Referrer",rows:e.top_referrers,cols:["ref","visitors","chats"]},null,8,["rows"])]),t("div",D,[s[3]||(s[3]=t("div",{class:"font-medium mb-2"},"Aktivität nach Stunde",-1)),t("div",L,[(p(!0),u(k,null,C(e.by_hour,(o,c)=>(p(),u("div",{key:c,class:"h-8 rounded",title:c+":00 → "+o,style:A({background:`rgba(59,130,246,${o/x.value||0})`})},T(c),13,M))),128))])])])}}});export{R as default};
