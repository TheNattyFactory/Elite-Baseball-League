/* Elite Baseball League — eblUnifiedAppearance */
(function(){
  const baseRenderer=window.eblCanonicalAvatarRenderer||window.eblPlayerArt;
  if(typeof baseRenderer!=='function')return;
  const esc=typeof window.escapeHtml==='function'?window.escapeHtml:(s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m])));
  const N=(v,d=1)=>{const q=Number(v);return Number.isFinite(q)?q:d};
  const UNIFIED_HAIR_COLORS=['#171411','#2b1b15','#4a2c1d','#6b4128','#8a5b34','#b07842','#d3a060','#9b9b9b','#e5e3dc'];
  const SKIN_COLORS=['#f2c59d','#e7b58d','#dca47b','#c98c68','#bd7c57','#8d573e','#754733','#633c2e'];
  const UNIFIED_EYE_COLORS=['#4b2d1f','#765133','#3d7b5a','#2f6690','#77736b','#18232d'];
  const FACE_SIDES={1:[111,189],2:[96,204],3:[113,187],4:[103,197],5:[110,190]};
  const APPEARANCE_KEYS=['face_id','skin_color_id','hair_id','hair_color_id','facial_hair_id','eye_color_id','nose_id','eye_shape_id','mouth_id','ear_size_id','eye_black_id','eyewear_id','chain_id','sleeve_id','body_build_id','jersey_number'];

  function creatorState(){try{return CREATOR}catch(_){return {}}}
  function creatorKey(p={}){
    const defaults={hair_color_id:3,eye_color_id:6,ear_size_id:2,jersey_number:24};
    const sig=APPEARANCE_KEYS.map(k=>String(N(p[k],defaults[k]??1))).join('|');
    let h=2166136261;for(let i=0;i<sig.length;i++){h^=sig.charCodeAt(i);h=Math.imul(h,16777619)}return (h>>>0)||1;
  }
  function creatorModel(extra={}){
    const src={...creatorState(),...(extra||{})},key=creatorKey(src);
    return {...src,id:-1600000000-key,player_id:-1600000000-key,username:`__ebl_creator_v61_${key}`,name:'EBL Creator Preview',appearance_json:null,appearance:null,avatar:null,_eblCreatorPreview:true};
  }
  function productionModel(raw={}){
    if(raw?._eblCreatorPreview)return raw;
    try{return typeof window.eblResolveCanonicalPlayerIdentity==='function'?window.eblResolveCanonicalPlayerIdentity(raw||{}):(raw||{})}catch(_){return raw||{}}
  }
  function hairUnderCap(p={}){
    const id=Math.max(1,Math.min(8,N(p.hair_id,1)));if(id===1)return '';
    const fid=Math.max(1,Math.min(5,N(p.face_id,1))),lr=FACE_SIDES[fid]||FACE_SIDES[1],l=lr[0],r=lr[1];
    const c=UNIFIED_HAIR_COLORS[Math.max(0,Math.min(UNIFIED_HAIR_COLORS.length-1,N(p.hair_color_id,3)-1))];
    if(id===2)return `<g data-ebl-hair-under-cap="v63" fill="${c}"><path d="M${l-1} 116Q${l-5} 127 ${l} 143Q${l+4} 135 ${l+8} 124L${l+8} 116Z"/><path d="M${r+1} 116Q${r+5} 127 ${r} 143Q${r-4} 135 ${r-8} 124L${r-8} 116Z"/></g>`;
    if(id===3)return `<g data-ebl-hair-under-cap="v63" fill="${c}"><path d="M${l-3} 113Q${l-10} 136 ${l-7} 166Q${l-6} 184 ${l+1} 195Q${l+2} 171 ${l+11} 145L${l+10} 116Z"/><path d="M${r+3} 113Q${r+10} 136 ${r+7} 166Q${r+6} 184 ${r-1} 195Q${r-2} 171 ${r-11} 145L${r-10} 116Z"/></g>`;
    if(id===4)return `<g data-ebl-hair-under-cap="v63" fill="${c}"><path d="M${l-4} 112Q${l-13} 139 ${l-8} 176Q${l-4} 197 ${l+5} 207Q${l+3} 173 ${l+13} 143L${l+10} 115Z"/><path d="M${r+4} 112Q${r+13} 139 ${r+8} 176Q${r+4} 197 ${r-5} 207Q${r-3} 173 ${r-13} 143L${r-10} 115Z"/></g>`;
    if(id===5)return `<g data-ebl-hair-under-cap="v63" fill="none" stroke="${c}" stroke-width="10" stroke-linecap="round"><path d="M${l+4} 117Q${l-9} 143 ${l-2} 169Q${l+5} 189 ${l-2} 208"/><path d="M${r-4} 117Q${r+9} 143 ${r+2} 169Q${r-5} 189 ${r+2} 208"/></g>`;
    if(id===6)return `<g data-ebl-hair-under-cap="v63" fill="${c}"><path d="M${l-5} 111Q${l-15} 143 ${l-10} 184Q${l-8} 209 ${l+7} 226Q${l+7} 183 ${l+14} 145L${l+10} 114Z"/><path d="M${r+5} 111Q${r+15} 143 ${r+10} 184Q${r+8} 209 ${r-7} 226Q${r-7} 183 ${r-14} 145L${r-10} 114Z"/></g>`;
    if(id===7)return `<g data-ebl-hair-under-cap="v104" fill="none" stroke="${c}" stroke-width="9" stroke-linecap="round"><path d="M${l+4} 117Q${l-10} 137 ${l-1} 153T${l-1} 182T${l+1} 214"/><path d="M${l+12} 121Q${l+1} 143 ${l+9} 159T${l+8} 192"/><path d="M${r-4} 117Q${r+10} 137 ${r+1} 153T${r+1} 182T${r-1} 214"/><path d="M${r-12} 121Q${r-1} 143 ${r-9} 159T${r-8} 192"/></g>`;
    return `<g data-ebl-hair-under-cap="v104" fill="none" stroke="${c}" stroke-width="7.4" stroke-linecap="round"><path d="M${l+5} 116Q${l-3} 141 ${l-1} 218"/><path d="M${l+12} 118Q${l+4} 148 ${l+7} 225"/><path d="M${l+19} 122Q${l+12} 151 ${l+15} 211"/><path d="M${r-5} 116Q${r+3} 141 ${r+1} 218"/><path d="M${r-12} 118Q${r-4} 148 ${r-7} 225"/><path d="M${r-19} 122Q${r-12} 151 ${r-15} 211"/></g>`;
  }
  /* RC160: sculpted, style-specific under-cap hair on the one canonical SVG.
     All eight existing hairstyle IDs remain unchanged, including bald. */
  function hairSilhouetteFinish(p={}){
    const id=Math.max(1,Math.min(8,N(p.hair_id,1)));
    if(id===1)return '';
    const face=Math.max(1,Math.min(5,N(p.face_id,1))),sides=FACE_SIDES[face]||FACE_SIDES[1],l=sides[0],r=sides[1];
    const hair=UNIFIED_HAIR_COLORS[Math.max(0,Math.min(8,N(p.hair_color_id,3)-1))];
    const mirror=(d)=>d;
    let detail='';
    if(id===2){
      detail=`<path d="M${l+1} 118Q${l-4} 126 ${l+1} 135M${r-1} 118Q${r+4} 126 ${r-1} 135" fill="none" stroke="#fff" stroke-opacity=".13" stroke-width="1.4" stroke-linecap="round"/>`;
    } else if(id===3){
      detail=`<path d="M${l-4} 124Q${l-9} 146 ${l-4} 165T${l} 184M${r+4} 124Q${r+9} 146 ${r+4} 165T${r} 184" fill="none" stroke="#fff" stroke-opacity=".11" stroke-width="2.1" stroke-linecap="round"/><path d="M${l-1} 143Q${l+2} 152 ${l-3} 159M${r+1} 143Q${r-2} 152 ${r+3} 159" fill="none" stroke="#10101a" stroke-opacity=".22" stroke-width="1.8" stroke-linecap="round"/>`;
    } else if(id===4){
      detail=`<path d="M${l-8} 132Q${l-12} 159 ${l-6} 181Q${l-4} 190 ${l+1} 198M${r+8} 132Q${r+12} 159 ${r+6} 181Q${r+4} 190 ${r-1} 198" fill="none" stroke="#fff" stroke-opacity=".13" stroke-width="2.1" stroke-linecap="round"/><path d="M${l-1} 154Q${l-7} 182 ${l+2} 206M${r+1} 154Q${r+7} 182 ${r-2} 206" stroke="#090b10" stroke-opacity=".21" stroke-width="2" fill="none" stroke-linecap="round"/>`;
    } else if(id===5){
      const curls=[];
      for(let t=0;t<4;t++){
        const y=136+t*16,shift=(t%2)*3;
        curls.push(`<path d="M${l+1-shift} ${y}q-7 4 -3 11q5 5 8 -1M${r-1+shift} ${y}q7 4 3 11q-5 5 -8 -1" stroke="${hair}" stroke-width="5.3" fill="none" stroke-linecap="round"/><path d="M${l+1-shift} ${y+2}q-3 3 -1 7M${r-1+shift} ${y+2}q3 3 1 7" fill="none" stroke="#fff" stroke-opacity=".13" stroke-width="1.3" stroke-linecap="round"/>`);
      }
      detail=curls.join('');
    } else if(id===6){
      detail=`<path d="M${l-8} 143Q${l-16} 179 ${l-5} 209M${r+8} 143Q${r+16} 179 ${r+5} 209" fill="none" stroke="#fff" stroke-opacity=".12" stroke-width="2.8" stroke-linecap="round"/><path d="M${l-1} 145Q${l-11} 192 ${l+7} 223M${r+1} 145Q${r+11} 192 ${r-7} 223" fill="none" stroke="#080d13" stroke-opacity=".22" stroke-width="2.4" stroke-linecap="round"/>`;
    } else if(id===7){
      const bands=[];
      for(let t=0;t<5;t++){
        const y=146+t*13,x1=l-1+((t%2)*2),x2=r+1-((t%2)*2);
        bands.push(`<path d="M${x1-4} ${y}l8 4M${x2+4} ${y}l-8 4" fill="none" stroke="#e2d0ad" stroke-opacity=".22" stroke-width="2.5" stroke-linecap="round"/>`);
      }
      detail=bands.join('');
    } else {
      const marks=[];
      for(let t=0;t<3;t++){
        const off=t*9, y=147+t*5;
        marks.push(`<path d="M${l+4+off} ${y}Q${l-2+off} ${y+28} ${l+3+off} ${y+64}M${r-4-off} ${y}Q${r+2-off} ${y+28} ${r-3-off} ${y+64}" fill="none" stroke="#fff" stroke-opacity=".105" stroke-width="1.8" stroke-linecap="round"/>`);
      }
      detail=marks.join('');
    }
    return `<g data-ebl-hair-finish="rc160" pointer-events="none">${detail}</g>`;
  }
  function eyeBlack(p={}){
    const id=Math.max(1,Math.min(5,N(p.eye_black_id,1)));if(id===1)return '';
    if(id===2)return `<g data-ebl-eye-black="v63" fill="none" stroke="#111317" stroke-width="5.4" stroke-linecap="round" opacity=".96"><path d="M113 157Q124 160 136 159"/><path d="M164 159Q176 160 187 157"/></g>`;
    if(id===3)return `<g data-ebl-eye-black="v63" fill="none" stroke="#111317" stroke-width="3.7" stroke-linecap="round" opacity=".96"><path d="M113 154Q124 157 136 156"/><path d="M113 162Q124 165 135 164"/><path d="M164 156Q176 157 187 154"/><path d="M165 164Q176 165 187 162"/></g>`;
    if(id===4)return `<g data-ebl-eye-black="v63" fill="#111317" opacity=".96"><path d="M118 155L134 158L126 169Z"/><path d="M166 158L182 155L174 169Z"/></g>`;
    return `<g data-ebl-eye-black="v63" fill="none" stroke="#111317" stroke-width="3.8" stroke-linecap="round" opacity=".96"><path d="M121 155V169M116 162H126M179 155V169M174 162H184"/></g>`;
  }
  function earMarkup(p={},side='left'){
    const id=Math.max(1,Math.min(4,N(p.ear_size_id,2))),skin=SKIN_COLORS[Math.max(0,Math.min(7,N(p.skin_color_id,1)-1))];
    const spec=id===1?{rx:7,ry:12,cxL:107,cxR:193}:id===3?{rx:11,ry:18,cxL:103,cxR:197}:id===4?{rx:12.5,ry:19.5,cxL:100.5,cxR:199.5}:{rx:9,ry:15,cxL:105,cxR:195};
    const cx=side==='left'?spec.cxL:spec.cxR,inner=side==='left'?cx+1:cx-1,arc=side==='left'?`M${inner+1} 139Q${inner-4} 145 ${inner+1} 151`:`M${inner-1} 139Q${inner+4} 145 ${inner-1} 151`;
    return `<g data-ebl-ear="v63"><ellipse cx="${cx}" cy="145" rx="${spec.rx}" ry="${spec.ry}" fill="${skin}" stroke="#2a1712" stroke-width="2.7"/><path d="${arc}" fill="none" stroke="#9a5c4d" stroke-width="1.5" stroke-linecap="round" opacity=".55"/></g>`;
  }
  /* RC159: existing appearance IDs now also control subtle brows and face planes.
     Nothing new is stored in the player identity or added to the creator schema. */
  function complexionInk(p={}){
    const i=Math.max(1,Math.min(8,N(p.skin_color_id,1)));
    return ['#9a6250','#935b49','#86503f','#754536','#6c3d31','#4b2923','#38221e','#30201c'][i-1];
  }
  function eyebrowMarkup(p={}){
    const kind=Math.max(1,Math.min(6,N(p.eye_shape_id,1)));
    const c=UNIFIED_HAIR_COLORS[Math.max(0,Math.min(8,N(p.hair_color_id,3)-1))];
    const forms={
      1:['M116 132Q127 127 139 131','M161 131Q173 127 184 132',3.5],
      2:['M115 134Q127 132 140 134','M160 134Q173 132 185 134',4.3],
      3:['M115 130Q127 122 139 127','M161 127Q173 122 185 130',3.5],
      4:['M114 128Q128 132 140 134','M160 134Q172 132 186 128',4.1],
      5:['M117 134Q128 130 138 132','M162 132Q172 130 183 134',2.6],
      6:['M113 130Q127 125 142 128','M158 128Q173 125 187 130',4.8]
    }[kind];
    return `<g data-ebl-brows="rc159" fill="none" stroke="${c}" stroke-linecap="round"><path d="${forms[0]}" stroke-width="${forms[2]}"/><path d="${forms[1]}" stroke-width="${forms[2]}"/></g>`;
  }
  function eyeMarkup(p={}){
    const id=Math.max(1,Math.min(6,N(p.eye_shape_id,1))),ec=UNIFIED_EYE_COLORS[Math.max(0,Math.min(5,N(p.eye_color_id,6)-1))];
    const shapes={
      1:['M116 145Q128 138 140 145Q128 152 116 145Z','M160 145Q172 138 184 145Q172 152 160 145Z',4,4.4],
      2:['M116 145Q128 141 140 145Q128 149 116 145Z','M160 145Q172 141 184 145Q172 149 160 145Z',4.2,3.2],
      3:['M117 145Q128 136 139 145Q128 154 117 145Z','M161 145Q172 136 183 145Q172 154 161 145Z',4.4,4.9],
      4:['M116 146Q128 139 140 145Q128 151 116 146Z','M160 145Q172 139 184 146Q172 151 160 145Z',4,4],
      5:['M116 145Q128 140 140 144Q128 150 116 145Z','M160 144Q172 140 184 145Q172 150 160 144Z',3.6,3.5],
      6:['M113 145Q128 136 143 145Q128 153 113 145Z','M157 145Q172 136 187 145Q172 153 157 145Z',4.5,4.5]
    }[id];
    return `<g data-ebl-eyes="v63"><path d="${shapes[0]}" fill="#fff" stroke="${complexionInk(p)}" stroke-width="1.8"/><path d="${shapes[1]}" fill="#fff" stroke="${complexionInk(p)}" stroke-width="1.8"/><ellipse cx="128" cy="145" rx="${shapes[2]}" ry="${shapes[3]}" fill="${ec}"/><ellipse cx="172" cy="145" rx="${shapes[2]}" ry="${shapes[3]}" fill="${ec}"/><circle cx="128" cy="145" r="1.45" fill="#111317"/><circle cx="172" cy="145" r="1.45" fill="#111317"/><circle cx="126.8" cy="143.7" r=".75" fill="#fff" opacity=".75"/><circle cx="170.8" cy="143.7" r=".75" fill="#fff" opacity=".75"/></g>`;
  }
  function noseMarkup(p={}){
    const id=Math.max(1,Math.min(6,N(p.nose_id,1)));
    if(id===2)return `<path data-ebl-nose="v63" d="M150 151Q146 162 147 168Q150 172 154 169Q156 167 158 168" fill="none" stroke="${complexionInk(p)}" stroke-width="2.35" stroke-linecap="round"/>`;
    if(id===3)return `<path data-ebl-nose="v63" d="M150 147L147 166Q147 172 153 173Q157 173 159 170" fill="none" stroke="${complexionInk(p)}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>`;
    if(id===4)return `<path data-ebl-nose="v63" d="M150 148Q146 161 146 169Q150 174 155 171M143 171Q147 174 151 173M157 171Q160 173 163 170" fill="none" stroke="${complexionInk(p)}" stroke-width="2.2" stroke-linecap="round"/>`;
    if(id===5)return `<path data-ebl-nose="v104" d="M150 148Q148 158 148 168Q150 171 153 170M146 171Q150 173 154 171" fill="none" stroke="${complexionInk(p)}" stroke-width="2.05" stroke-linecap="round"/>`;
    if(id===6)return `<path data-ebl-nose="v104" d="M149 146Q154 154 151 162Q148 168 151 173Q155 176 160 171" fill="none" stroke="${complexionInk(p)}" stroke-width="2.35" stroke-linecap="round"/>`;
    return `<path data-ebl-nose="v63" d="M150 147Q144 164 148 171Q153 175 158 171" fill="none" stroke="${complexionInk(p)}" stroke-width="2.35" stroke-linecap="round"/>`;
  }
  function mouthMarkup(p={}){
    const id=Math.max(1,Math.min(6,N(p.mouth_id,1)));
    if(id===2)return `<path data-ebl-mouth="v63" d="M135 184Q150 193 165 184" fill="none" stroke="${complexionInk(p)}" stroke-width="2.9" stroke-linecap="round"/>`;
    if(id===3)return `<path data-ebl-mouth="v63" d="M131 183Q150 195 169 183Q163 191 150 192Q137 191 131 183Z" fill="#8a4a45" opacity=".92"/>`;
    if(id===4)return `<path data-ebl-mouth="v63" d="M136 186Q150 184 164 186" fill="none" stroke="${complexionInk(p)}" stroke-width="3" stroke-linecap="round"/>`;
    if(id===5)return `<path data-ebl-mouth="v104" d="M138 185Q150 187 162 185" fill="none" stroke="${complexionInk(p)}" stroke-width="2.1" stroke-linecap="round"/>`;
    if(id===6)return `<g data-ebl-mouth="v104"><path d="M133 184Q150 190 167 184Q160 194 150 194Q140 194 133 184Z" fill="#8a4a45" opacity=".88"/><path d="M136 185Q150 189 164 185" fill="none" stroke="#5e332e" stroke-width="1.5" stroke-linecap="round"/></g>`;
    return `<path data-ebl-mouth="v63" d="M134 184Q150 190 166 184" fill="none" stroke="${complexionInk(p)}" stroke-width="2.8" stroke-linecap="round"/>`;
  }
  /* RC158: illuminated face planes, never a separate face renderer.  The artwork
     reads at card size and at the much smaller roster/scoreboard sizes. */
  function facePolish(p={}){
    const fid=Math.max(1,Math.min(5,N(p.face_id,1)));
    const tone=Math.max(1,Math.min(8,N(p.skin_color_id,1)));
    const broad=(fid===2||fid===4),oval=fid===3,angular=fid===5;
    const ink=complexionInk(p),reflect=tone>=6?'#f4b78f':'#fff0d2';
    const cheek=broad?22:oval?15:17,jaw=broad?18:oval?13:angular?20:15;
    const spec={
      1:'M117 170Q122 180 131 184M183 170Q178 180 169 184',
      2:'M107 172Q116 188 132 190M193 172Q184 188 168 190',
      3:'M116 175Q121 195 137 207M184 175Q179 195 163 207',
      4:'M109 177Q120 188 131 190M191 177Q180 188 169 190',
      5:'M114 170Q124 187 134 192M186 170Q176 187 166 192'
    }[fid];
    return `<g data-ebl-face-polish="rc159" pointer-events="none">
      <ellipse cx="124" cy="161" rx="${cheek}" ry="24" fill="${reflect}" opacity="${tone>=6?'.10':'.065'}"/>
      <ellipse cx="178" cy="160" rx="${cheek-2}" ry="27" fill="${ink}" opacity=".065"/>
      <path d="${spec}" fill="none" stroke="${ink}" stroke-width="${broad?2.8:1.8}" opacity=".10" stroke-linecap="round"/>
      <path d="M115 152Q127 156 138 153M162 153Q174 156 185 152" fill="none" stroke="${ink}" stroke-width="1.2" opacity=".11" stroke-linecap="round"/>
      <path d="M148 147Q144 160 147 164" fill="none" stroke="${reflect}" stroke-width="1.8" opacity=".18" stroke-linecap="round"/>
      <path d="M138 196Q150 200 162 196" fill="none" stroke="${ink}" stroke-width="1.1" opacity=".10" stroke-linecap="round"/>
      ${angular?`<path d="M137 208Q150 212 163 208" fill="none" stroke="${ink}" stroke-width="1.6" opacity=".19"/>`:''}
    </g>`;
  }
  /* Six saved mouth shapes have small matching smile, focus, and lip details.
     No expression ID is stored: this is keyed to the player's existing mouth. */
  function expressionFinish(p={}){
    const id=Math.max(1,Math.min(6,N(p.mouth_id,1)));
    const ink=complexionInk(p),tone=Math.max(1,Math.min(8,N(p.skin_color_id,1)));
    const shine=tone>=6?'#f6bb94':'#fff2d9';
    let art='';
    if(id===1)art='<path d="M134 182q-4 -2 -5 -5M166 182q4 -2 5 -5"/>';
    if(id===2)art='<path d="M132 181q-5 -3 -5 -8M168 181q5 -3 5 -8"/><path d="M139 192Q150 196 161 192" opacity=".34"/>';
    if(id===3)art='<path d="M130 182q-6 -4 -6 -10M170 182q6 -4 6 -10"/><path d="M138 188Q150 194 162 188" opacity=".33"/>';
    if(id===4)art='<path d="M135 182Q150 180 165 182" opacity=".36"/>';
    if(id===5)art='<path d="M138 181Q150 183 162 181" opacity=".22"/>';
    if(id===6)art='<path d="M131 181q-5 -2 -6 -8M169 181q5 -2 6 -8"/><path d="M140 192Q150 196 160 192" opacity=".42"/>';
    return `<g data-ebl-expression="rc160" data-ebl-expression-id="${id}" pointer-events="none"><g stroke="${ink}" stroke-opacity=".29" stroke-width="1.5" stroke-linecap="round" fill="none">${art}</g>${[3,6].includes(id)?`<path d="M140 186Q150 189 160 186" stroke="${shine}" stroke-opacity=".18" stroke-width="1.2" stroke-linecap="round" fill="none"/>`:''}</g>`;
  }
  function capFabricFinish(p={}){
    return `<g data-ebl-cap-finish="rc158" fill="none" pointer-events="none" stroke-linecap="round">
      <path d="M112 103Q119 79 136 69" stroke="#fff" stroke-width="1.6" opacity=".12"/>
      <path d="M187 103Q181 78 165 69" stroke="#07101c" stroke-width="1.7" opacity=".18"/>
      <path d="M150 61L150 98" stroke="#fff" stroke-width="1.1" opacity=".10"/>
      <path d="M114 107Q150 98 186 107" stroke="#fff" stroke-width="1.25" opacity=".08" stroke-dasharray="2.5 4"/>
    </g>`;
  }
  function beardSurfaceFinish(p={}){
    const id=N(p.facial_hair_id,1);
    if(![3,4,8,12].includes(id))return '';
    const c=UNIFIED_HAIR_COLORS[Math.max(0,Math.min(UNIFIED_HAIR_COLORS.length-1,N(p.hair_color_id,3)-1))];
    return `<g data-ebl-beard-finish="rc159" fill="none" pointer-events="none" stroke-linecap="round">
      <path d="M120 183Q126 197 139 203" stroke="#fff" stroke-width="1.3" opacity=".075"/>
      <path d="M180 183Q174 197 161 203" stroke="#050505" stroke-width="1.6" opacity=".11"/>
      <path d="M139 205Q150 211 161 205" stroke="${c}" stroke-width="1.6" opacity=".32"/>
    </g>`;
  }
  function eyewear(p={}){
    const id=Math.max(1,Math.min(5,N(p.eyewear_id,1)));if(id===1)return '';
    if(id===2)return `<g data-ebl-eyewear="v63" fill="none" stroke="#16212b" stroke-width="3.6"><path d="M112 137Q127 130 143 137L141 151Q128 156 115 147Z"/><path d="M157 137Q173 130 188 137L185 147Q172 156 159 151Z"/><path d="M141 139Q150 135 159 139"/></g>`;
    if(id===3)return `<g data-ebl-eyewear="v63" fill="none" stroke="#26323c" stroke-width="2.3"><rect x="113" y="137" width="29" height="17" rx="4"/><rect x="158" y="137" width="29" height="17" rx="4"/><path d="M142 143Q150 139 158 143M113 141L105 138M187 141L195 138"/></g>`;
    if(id===4)return `<g data-ebl-eyewear="v63" fill="#dceaf3" fill-opacity=".08" stroke="#26323c" stroke-width="2.4"><circle cx="128" cy="145" r="13"/><circle cx="172" cy="145" r="13"/><path d="M141 143Q150 138 159 143" fill="none"/><path d="M115 141L105 138M185 141L195 138" fill="none"/></g>`;
    return `<g data-ebl-eyewear="v63" fill="#172531" fill-opacity=".18" stroke="#16212b" stroke-width="2.6"><path d="M110 138Q127 132 145 138L141 152Q127 158 114 149Z"/><path d="M155 138Q173 132 190 138L186 149Q173 158 159 152Z"/><path d="M143 140Q150 137 157 140" fill="none"/></g>`;
  }
  const FACE_PATHS={
    3:{
      from:'M118 107Q120 72 150 69Q180 72 182 107L181 163Q179 197 165 214Q157 223 150 226Q143 223 135 214Q121 197 119 163Z',
      to:'M113 108Q116 72 150 69Q184 72 187 108L186 163Q184 196 168 213Q159 222 150 225Q141 222 132 213Q116 196 114 163Z'
    },
    5:{
      from:'M108 108Q113 74 150 71Q187 74 192 108L188 155L176 188L150 220L124 188L112 155Z',
      to:'M109 108Q114 74 150 71Q186 74 191 108L188 156Q184 177 174 192L162 205L157 211L143 211L138 205L126 192Q116 177 112 156Z'
    }
  };
  const FACE_JAW={
    1:{l:116,r:184,top:163,ml:129,mr:171,chin:211},
    2:{l:101,r:199,top:165,ml:120,mr:180,chin:216},
    3:{l:114,r:186,top:165,ml:131,mr:169,chin:223},
    4:{l:106,r:194,top:168,ml:122,mr:178,chin:216},
    5:{l:113,r:187,top:160,ml:127,mr:173,chin:213}
  };
  function tuneFaceGeometry(out,p={}){
    const fid=Math.max(1,Math.min(5,N(p.face_id,1))),swap=FACE_PATHS[fid];
    return swap?String(out).replace(swap.from,swap.to):String(out);
  }
  function facialHair(p={}){
    const id=N(p.facial_hair_id,1);if(id===1)return '';
    const fid=Math.max(1,Math.min(5,N(p.face_id,1))),j=FACE_JAW[fid]||FACE_JAW[1];
    const c=UNIFIED_HAIR_COLORS[Math.max(0,Math.min(UNIFIED_HAIR_COLORS.length-1,N(p.hair_color_id,3)-1))];
    const mouthY=174, chin=j.chin, patchTop=Math.max(188,chin-26), lowerTop=patchTop+4;
    const must=`<path d="M132 ${mouthY}Q140 ${mouthY-6} 149 ${mouthY-1}Q151 ${mouthY} 152 ${mouthY-1}Q160 ${mouthY-6} 168 ${mouthY}Q160 ${mouthY+7} 151 ${mouthY+5}Q150 ${mouthY+7} 149 ${mouthY+5}Q140 ${mouthY+7} 132 ${mouthY}Z" fill="${c}"/>`;
    const mustCircle=`<path d="M132 ${mouthY+1}Q140 ${mouthY-7} 149 ${mouthY-2}Q151 ${mouthY-1} 152 ${mouthY-2}Q160 ${mouthY-7} 168 ${mouthY+1}Q160 ${mouthY+8} 151 ${mouthY+6}Q150 ${mouthY+8} 149 ${mouthY+6}Q140 ${mouthY+8} 132 ${mouthY+1}Z" fill="${c}"/>`;
    const handle=`<path d="M130 ${mouthY}Q139 ${mouthY-7} 147 ${mouthY-1}Q138 ${mouthY+9} 124 ${mouthY+7}Q118 ${mouthY+6} 114 ${mouthY+1}Q123 ${mouthY+5} 130 ${mouthY}ZM170 ${mouthY}Q161 ${mouthY-7} 153 ${mouthY-1}Q162 ${mouthY+9} 176 ${mouthY+7}Q182 ${mouthY+6} 186 ${mouthY+1}Q177 ${mouthY+5} 170 ${mouthY}Z" fill="${c}"/>`;
    const soul=`<path d="M144 ${patchTop+3}Q150 ${patchTop+8} 156 ${patchTop+3}L154 ${patchTop+13}Q150 ${patchTop+17} 146 ${patchTop+13}Z" fill="${c}"/>`;
    const goatee=`<g><path d="M140 ${lowerTop}Q150 ${lowerTop+5} 160 ${lowerTop}L158 ${Math.min(chin,lowerTop+24)}Q150 ${Math.min(chin+2,lowerTop+30)} 142 ${Math.min(chin,lowerTop+24)}Z" fill="${c}"/><path d="M142 ${lowerTop+1}Q150 ${lowerTop+7} 158 ${lowerTop+1}" fill="none" stroke="#000" stroke-opacity=".14" stroke-width="1"/></g>`;
    const jawPath=`M${j.l} ${j.top}Q${j.l+4} ${chin-24} ${j.ml} ${chin-10}Q140 ${chin-1} 150 ${chin+1}Q160 ${chin-1} ${j.mr} ${chin-10}Q${j.r-4} ${chin-24} ${j.r} ${j.top}`;

    /* hand-placed, asymmetric stubble. Stroke length, angle and opacity vary so
       it reads like beard growth instead of a repeated dash pattern. */
    const scruff=(density='light')=>{
      const heavy=density==='heavy', sw=heavy?1.75:1.32;
      const base=[
        [118,174,2.6,.8,.42],[124,178,3.5,1.4,.52],[131,181,2.2,.9,.46],[137,185,3.1,1.5,.58],[143,188,1.8,1.2,.44],
        [160,186,-2.7,1.1,.51],[166,183,-3.4,1.5,.57],[173,179,-2.1,.8,.43],[179,175,-3.0,1.0,.49],
        [121,185,2.3,1.6,.47],[128,190,3.2,1.0,.55],[134,194,2.0,1.7,.43],[141,197,2.6,1.3,.54],[147,199,1.3,2.2,.48],
        [153,198,-1.8,1.9,.52],[159,196,-2.4,1.1,.46],[165,192,-3.0,1.6,.56],[172,188,-2.2,1.0,.45],[177,184,-3.2,1.3,.50],
        [128,199,2.7,1.4,.44],[135,203,1.8,1.9,.49],[142,205,2.4,1.1,.55],[149,207,.8,2.1,.46],[156,205,-2.0,1.5,.52],[163,202,-2.8,1.0,.47],[170,198,-2.2,1.6,.54],
        [135,174,1.7,.7,.30],[140,175,2.5,.9,.38],[146,176,1.4,.6,.33],[151,175,1.0,.8,.28],[156,176,-1.8,.7,.36],[162,174,-2.3,.9,.31]
      ];
      if(heavy)base.push(
        [115,169,3.0,1.1,.48],[121,172,2.2,1.6,.52],[183,170,-2.6,1.4,.50],[178,173,-3.2,.9,.45],
        [118,181,3.3,1.5,.56],[124,193,2.7,1.7,.54],[132,198,2.0,1.0,.48],[168,197,-2.5,1.6,.57],[176,191,-3.1,1.0,.52],[182,180,-2.4,1.8,.49],
        [137,208,2.1,1.2,.46],[145,210,1.4,1.9,.55],[153,209,-1.7,1.2,.50],[161,207,-2.2,1.7,.47],
        [132,176,2.4,.8,.38],[144,178,1.7,.9,.44],[158,177,-2.0,.8,.41],[168,175,-2.5,1.0,.36]
      );
      const hairs=base.map(([x,y,dx,dy,a])=>`<path d="M${x} ${y}l${dx} ${dy}" stroke-opacity="${heavy?Math.min(.78,a+.12):a}"/>`).join('');
      const lip=heavy
        ? `<path d="M135 173Q143 169 149 172M151 172Q158 169 165 173" stroke-opacity=".34" stroke-width="1.55"/>`
        : `<path d="M138 173Q144 170 149 172M152 172Q157 170 162 173" stroke-opacity=".22" stroke-width="1.2"/>`;
      return `<g fill="none" stroke="${c}" stroke-width="${sw}" stroke-linecap="round">${hairs}${lip}</g>`;
    };

    if(id===2)return `<g data-ebl-facial-hair="v61">${scruff('light')}</g>`;
    if(id===3)return `<g data-ebl-facial-hair="v61">${must}${goatee}</g>`;
    if(id===5)return `<g data-ebl-facial-hair="v61">${must}</g>`;
    if(id===4)return `<g data-ebl-facial-hair="v61">
      <path d="M${j.l-3} ${j.top-4}Q${j.l-4} ${chin-26} ${j.ml-2} ${chin-10}Q140 ${chin+1} 150 ${chin+4}Q160 ${chin+1} ${j.mr+2} ${chin-10}Q${j.r+4} ${chin-26} ${j.r+3} ${j.top-4}L${j.r-6} ${j.top+13}Q${j.r-10} ${mouthY+10} 168 ${mouthY+7}Q160 ${patchTop+2} 150 ${patchTop+6}Q140 ${patchTop+2} 132 ${mouthY+7}Q${j.l+10} ${mouthY+10} ${j.l+6} ${j.top+13}Z" fill="${c}"/>
      ${must}
      <path d="M131 ${mouthY+2}Q134 ${patchTop+1} 141 ${patchTop+7}M169 ${mouthY+2}Q166 ${patchTop+1} 159 ${patchTop+7}" fill="none" stroke="${c}" stroke-width="7.8" stroke-linecap="round"/>
      <g fill="none" stroke="#fff" stroke-opacity=".055" stroke-width="1.1" stroke-linecap="round"><path d="M${j.l} ${j.top+11}l4 3M${j.l+3} ${j.top+22}l4 2M${j.r} ${j.top+12}l-4 3M${j.r-3} ${j.top+23}l-4 2"/></g>
    </g>`;
    if(id===6)return `<g data-ebl-facial-hair="v61">${scruff('heavy')}</g>`;
    if(id===7)return `<path data-ebl-facial-hair="v61" d="${jawPath}" fill="none" stroke="${c}" stroke-width="5.8" stroke-linecap="round" stroke-linejoin="round"/>`;
    if(id===8)return `<g data-ebl-facial-hair="v61">
      <path d="M${j.l+1} ${j.top+4}Q${j.l+3} ${chin-21} ${j.ml} ${chin-10}Q140 ${chin-2} 150 ${chin+1}Q160 ${chin-2} ${j.mr} ${chin-10}Q${j.r-3} ${chin-21} ${j.r-1} ${j.top+4}L${j.r-8} ${j.top+15}Q${j.r-12} ${mouthY+11} 166 ${mouthY+8}Q159 ${patchTop+1} 150 ${patchTop+5}Q141 ${patchTop+1} 134 ${mouthY+8}Q${j.l+12} ${mouthY+11} ${j.l+8} ${j.top+15}Z" fill="${c}"/>
      <path d="M126 ${mouthY+1}Q137 ${mouthY-7} 147 ${mouthY-3}Q150 ${mouthY-1} 153 ${mouthY-3}Q163 ${mouthY-7} 174 ${mouthY+1}Q165 ${mouthY+8} 153 ${mouthY+6}Q150 ${mouthY+8} 147 ${mouthY+6}Q135 ${mouthY+8} 126 ${mouthY+1}Z" fill="${c}"/>
      <path d="M132 ${mouthY+3}Q136 ${patchTop+1} 142 ${patchTop+6}M168 ${mouthY+3}Q164 ${patchTop+1} 158 ${patchTop+6}" fill="none" stroke="${c}" stroke-width="6.2" stroke-linecap="round"/>
    </g>`;
    if(id===11)return `<g data-ebl-facial-hair="v61">${soul}</g>`;
    if(id===12)return `<g data-ebl-facial-hair="v61">${mustCircle}<path d="M136 ${mouthY+1}Q136 ${patchTop+5} 143 ${patchTop+9}Q150 ${patchTop+13} 157 ${patchTop+9}Q164 ${patchTop+5} 164 ${mouthY+1}" fill="none" stroke="${c}" stroke-width="6.4" stroke-linecap="round" stroke-linejoin="round"/><path d="M141 ${patchTop+8}Q150 ${patchTop+14} 159 ${patchTop+8}L157 ${Math.min(chin,patchTop+25)}Q150 ${Math.min(chin+3,patchTop+31)} 143 ${Math.min(chin,patchTop+25)}Z" fill="${c}"/></g>`;
    if(id===13)return `<g data-ebl-facial-hair="v61">${handle}</g>`;
    if(id===10)return `<g data-ebl-facial-hair="v61"><path d="M130 ${mouthY}Q139 ${mouthY-7} 147 ${mouthY-1}Q138 ${mouthY+7} 123 ${mouthY+6}Q118 ${mouthY+5} 114 ${mouthY+1}Q123 ${mouthY+5} 130 ${mouthY}ZM170 ${mouthY}Q161 ${mouthY-7} 153 ${mouthY-1}Q162 ${mouthY+7} 177 ${mouthY+6}Q182 ${mouthY+5} 186 ${mouthY+1}Q177 ${mouthY+5} 170 ${mouthY}Z" fill="${c}"/><path d="M141 ${patchTop+7}Q150 ${patchTop+11} 159 ${patchTop+7}L156 ${Math.min(chin,patchTop+26)}Q150 ${Math.min(chin+4,patchTop+36)} 144 ${Math.min(chin,patchTop+26)}Z" fill="${c}"/></g>`;
    if(id===14)return `<g data-ebl-facial-hair="v61"><path d="M${j.l} ${j.top}Q${j.l+2} ${chin-22} ${j.ml-2} ${chin-12}" fill="none" stroke="${c}" stroke-width="10" stroke-linecap="round"/><path d="M${j.r} ${j.top}Q${j.r-2} ${chin-22} ${j.mr+2} ${chin-12}" fill="none" stroke="${c}" stroke-width="10" stroke-linecap="round"/></g>`;
    return '';
  }
  function chainMarkup(p={}){
    const id=Math.max(1,Math.min(7,N(p.chain_id,1)));if(id===1)return '';
    const gold={metal:'#efc652',shadow:'#665019',shine:'#fff1a8'};
    const silver={metal:'#d7dce3',shadow:'#59616d',shine:'#ffffff'};
    const one=(y,metal,large=false)=>{
      const x1=large?116:123,x2=large?184:177,drop=large?27:20;
      const w=large?6.8:4.4,sw=large?9.2:6.3,hi=large?2.0:1.35;
      const dash=large?'3.1 4.4':'2.0 3.7';
      return `<path d="M${x1} ${y}Q150 ${y+drop} ${x2} ${y}" fill="none" stroke="${metal.shadow}" stroke-opacity=".34" stroke-width="${sw}" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M${x1} ${y}Q150 ${y+drop} ${x2} ${y}" fill="none" stroke="${metal.metal}" stroke-width="${w}" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M${x1+2} ${y+1}Q150 ${y+drop-2} ${x2-2} ${y+1}" fill="none" stroke="${metal.shine}" stroke-width="${hi}" stroke-dasharray="${dash}" stroke-opacity=".82" stroke-linecap="round"/>`;
    };
    let art='';
    if(id===2)art=one(240,gold,false);
    if(id===3)art=one(238,gold,false)+one(248,gold,false);
    if(id===4)art=one(240,silver,false);
    if(id===5)art=one(238,silver,false)+one(248,silver,false);
    if(id===6)art=one(238,gold,true);
    if(id===7)art=one(238,silver,true);
    return `<g data-ebl-chain="v67">${art}</g>`;
  }
  function applyBodyBuildGeometry(out,p={}){
    const build=Math.max(1,Math.min(3,N(p.body_build_id,1)));
    const skin=SKIN_COLORS[Math.max(0,Math.min(7,N(p.skin_color_id,1)-1))];
    const geo={
      1:{
        armL:'M53 309Q61 314 75 318L72 360H46L47 342Q49 324 53 309Z',armR:'M247 309Q239 314 225 318L228 360H254L253 342Q251 324 247 309Z',
        neck:'M132 196Q132 207 133 218L132 231Q150 236 168 231L167 218Q168 207 168 196Z',
        body:'M69 360L77 299Q81 271 111 248L126 239H174L189 248Q219 271 223 299L231 360Z',
        sleeveL:'M112 247Q95 250 78 260Q59 271 50 288L44 304Q59 311 79 313Q84 299 92 281Q101 260 112 247Z',
        sleeveR:'M188 247Q205 250 222 260Q241 271 250 288L256 304Q241 311 221 313Q216 299 208 281Q199 260 188 247Z',
        shoulder:'M58 286Q80 266 110 251M242 286Q220 266 190 251',hem:'M46 303Q61 310 79 311M254 303Q239 310 221 311',hem2:'M47 302Q62 308 79 309M253 302Q238 308 221 309',
        collar:'M128 234Q150 245 172 234',collar2:'M129 235Q150 243 171 235'
      },
      2:{
        armL:'M38 307Q52 313 77 319L73 360H29L31 339Q33 319 38 307Z',armR:'M262 307Q248 313 223 319L227 360H271L269 339Q267 319 262 307Z',
        neck:'M121 195Q122 208 123 220L121 233Q150 243 179 233L177 220Q178 208 179 195Z',
        body:'M55 360L61 299Q64 266 101 243L120 235H180L199 243Q236 266 239 299L245 360Z',
        sleeveL:'M105 243Q79 245 57 258Q38 270 29 288L24 305Q47 315 74 316Q79 297 88 278Q96 255 105 243Z',
        sleeveR:'M195 243Q221 245 243 258Q262 270 271 288L276 305Q253 315 226 316Q221 297 212 278Q204 255 195 243Z',
        shoulder:'M40 287Q69 258 105 247M260 287Q231 258 195 247',hem:'M26 304Q48 314 74 314M274 304Q252 314 226 314',hem2:'M27 303Q49 312 74 312M273 303Q251 312 226 312',
        collar:'M121 233Q150 247 179 233',collar2:'M122 234Q150 245 178 234'
      },
      3:{
        armL:'M42 306Q55 309 69 314Q79 318 84 324L78 360H35L37 341Q37 323 42 306Z',armR:'M258 306Q245 309 231 314Q221 318 216 324L222 360H265L263 341Q263 323 258 306Z',
        neck:'M125 195Q126 207 127 217L125 231Q137 238 150 239Q163 238 175 231L173 217Q174 207 175 195Z',
        body:'M80 360L70 304Q67 271 108 242L124 234H176L192 242Q233 271 230 304L220 360Z',
        sleeveL:'M108 242Q84 245 63 258Q44 271 36 287L31 303Q51 312 75 314Q79 295 89 276Q98 254 108 242Z',
        sleeveR:'M192 242Q216 245 237 258Q256 271 264 287L269 303Q249 312 225 314Q221 295 211 276Q202 254 192 242Z',
        shoulder:'M44 286Q72 258 108 246M256 286Q228 258 192 246',hem:'M33 302Q52 312 75 312M267 302Q248 312 225 312',hem2:'M34 301Q53 310 75 310M266 301Q247 310 225 310',
        collar:'M124 233Q150 245 176 233',collar2:'M125 234Q150 243 175 234'
      }
    }[build];
    out=out.replace(/<path data-ebl-arm="left" d="[^"]+" fill="[^"]+" stroke="#2a1712" stroke-width="3\.5"\/>/,`<path data-ebl-arm="left" d="${geo.armL}" fill="${skin}" stroke="#2a1712" stroke-width="3.5"/>`);
    out=out.replace(/<path data-ebl-arm="right" d="[^"]+" fill="[^"]+" stroke="#2a1712" stroke-width="3\.5"\/>/,`<path data-ebl-arm="right" d="${geo.armR}" fill="${skin}" stroke="#2a1712" stroke-width="3.5"/>`);
    out=out.replace(/<path data-ebl-neck="v54" d="[^"]+" fill="[^"]+" stroke="#2a1712" stroke-width="3"\/>/,`<path data-ebl-neck="v54" d="${geo.neck}" fill="${skin}" stroke="#2a1712" stroke-width="3"/>`);
    out=out.replace(/(<path data-ebl-jersey-body="v55" d=")[^"]+(" )/,(m,a,b)=>a+geo.body+b);
    out=out.replace(/(<path data-ebl-jersey-sleeve="left-v55" d=")[^"]+(" )/,(m,a,b)=>a+geo.sleeveL+b);
    out=out.replace(/(<path data-ebl-jersey-sleeve="right-v55" d=")[^"]+(" )/,(m,a,b)=>a+geo.sleeveR+b);
    out=out.replaceAll('M58 286Q80 266 110 251M242 286Q220 266 190 251',geo.shoulder);
    out=out.replaceAll('M46 303Q61 310 79 311M254 303Q239 310 221 311',geo.hem);
    out=out.replaceAll('M47 302Q62 308 79 309M253 302Q238 308 221 309',geo.hem2);
    out=out.replaceAll('M128 234Q150 245 172 234',geo.collar);
    out=out.replaceAll('M129 235Q150 243 171 235',geo.collar2);
    return out;
  }
  function bodyBuildMarkup(p={}){
    const build=Math.max(1,Math.min(3,N(p.body_build_id,1)));
    if(build===2)return `<g data-ebl-body-build="v102" pointer-events="none"><path d="M70 281Q91 258 120 247M230 281Q209 258 180 247" fill="none" stroke="#000" stroke-opacity=".10" stroke-width="2.4" stroke-linecap="round"/><path d="M91 334Q150 346 209 334" fill="none" stroke="#000" stroke-opacity=".07" stroke-width="2.2" stroke-linecap="round"/></g>`;
    if(build===3)return `<g data-ebl-body-build="v102" pointer-events="none"><path d="M72 278Q96 250 124 242M228 278Q204 250 176 242" fill="none" stroke="#fff" stroke-opacity=".15" stroke-width="2.5" stroke-linecap="round"/><path d="M114 258Q150 274 186 258" fill="none" stroke="#000" stroke-opacity=".10" stroke-width="2.2" stroke-linecap="round"/><path d="M93 340Q150 327 207 340" fill="none" stroke="#07101c" stroke-opacity=".10" stroke-width="2.1" stroke-linecap="round"/></g>`;
    return '';
  }
  function compressionSleeveMarkup(p={}){
    const sleeve=Math.max(1,Math.min(4,N(p.sleeve_id,1)));
    if(sleeve<=1)return '';
    const build=Math.max(1,Math.min(3,N(p.body_build_id,1)));
    const arms={
      1:{
        left:'M53 309Q61 314 75 318L72 360H46L47 342Q49 324 53 309Z',
        right:'M247 309Q239 314 225 318L228 360H254L253 342Q251 324 247 309Z',
        hiL:'M54 315Q62 319 73 321',hiR:'M246 315Q238 319 227 321'
      },
      2:{
        left:'M38 307Q52 313 77 319L73 360H29L31 339Q33 319 38 307Z',
        right:'M262 307Q248 313 223 319L227 360H271L269 339Q267 319 262 307Z',
        hiL:'M40 314Q54 319 75 322',hiR:'M260 314Q246 319 225 322'
      },
      3:{
        left:'M42 306Q55 309 69 314Q79 318 84 324L78 360H35L37 341Q37 323 42 306Z',
        right:'M258 306Q245 309 231 314Q221 318 216 324L222 360H265L263 341Q263 323 258 306Z',
        hiL:'M44 313Q58 315 71 320Q77 322 81 326',hiR:'M256 313Q242 315 229 320Q223 322 219 326'
      }
    }[build];
    const left=sleeve===2||sleeve===4,right=sleeve===3||sleeve===4;
    let out='';
    if(left)out+=`<g data-ebl-accessory="left-compression-sleeve-v112"><path d="${arms.left}" fill="#111827" stroke="#07101c" stroke-width="1.8" opacity=".98"/><path d="${arms.hiL}" fill="none" stroke="#ffffff" stroke-opacity=".11" stroke-width="1.5" stroke-linecap="round"/></g>`;
    if(right)out+=`<g data-ebl-accessory="right-compression-sleeve-v112"><path d="${arms.right}" fill="#111827" stroke="#07101c" stroke-width="1.8" opacity=".98"/><path d="${arms.hiR}" fill="none" stroke="#ffffff" stroke-opacity=".11" stroke-width="1.5" stroke-linecap="round"/></g>`;
    return out;
  }
  function finalAppearancePass(html,p={},action='portrait'){
    let out=String(html||'');
    if(!out||!(/^(portrait|auto)?$/i.test(String(action||'portrait'))))return out;
    // current owns final face geometry, facial hair, under-cap hair, and eye black.
    out=out.replace(/<path d="M112 154L136 158M164 158L188 154" stroke="#111" stroke-width="6" stroke-linecap="round" opacity="\.92"\/>/g,'')
           .replace(/<path d="M112 151L136 155M112 160L135 163M164 155L188 151M165 163L188 160" stroke="#111" stroke-width="4" stroke-linecap="round" opacity="\.92"\/>/g,'')
           .replace(/<g fill="none" stroke="#16212b" stroke-width="4"><path d="M112 137Q127 130 143 137L141 151Q128 156 115 147Z"\/><path d="M157 137Q173 130 188 137L185 147Q172 156 159 151Z"\/><path d="M141 139Q150 135 159 139"\/><\/g>/g,'')
           .replace(/<g data-ebl-hair-under-cap="v6[13]"[\s\S]*?<\/g>/g,'')
           .replace(/<g data-ebl-eye-black="v6[13]"[\s\S]*?<\/g>/g,'')
           .replace(/<g data-ebl-eyewear="v63"[\s\S]*?<\/g>/g,'')
           .replace(/<g data-ebl-accessory="(?:left|right)-compression-sleeve-v(?:54|112)"[\s\S]*?<\/g>/g,'')
           .replace(/<g data-ebl-facial-hair="v61"[\s\S]*?<\/g>/g,'')
           .replace(/<path data-ebl-facial-hair="v61"[^>]*\/>/g,'');
    /* A light crown fabric treatment on the *same* fitted team cap. */
    out=out.replace(/(<path data-ebl-cap-crown=[^>]*\/>)/, '$1'+capFabricFinish(p));
    out=applyBodyBuildGeometry(out,p);
    out=tuneFaceGeometry(out,p);
    out=out.replace(/<path d="M116 132Q127 126 139 131M161 131Q173 126 184 132" fill="none" stroke="[^"]+" stroke-width="4" stroke-linecap="round"\/>/,eyebrowMarkup(p));
    out=out.replace(/<ellipse cx="105" cy="145" rx="9" ry="15" fill="[^"]+" stroke="#2a1712" stroke-width="3"\/>/,earMarkup(p,'left'))
           .replace(/<ellipse cx="195" cy="145" rx="9" ry="15" fill="[^"]+" stroke="#2a1712" stroke-width="3"\/>/,earMarkup(p,'right'))
           .replace(/<path d="M116 145Q128 138 140 145Q128 152 116 145ZM160 145Q172 138 184 145Q172 152 160 145Z" fill="#fff" stroke="#2a1712" stroke-width="2"\/><ellipse cx="128" cy="145" rx="4" ry="4\.4" fill="[^"]+"\/><ellipse cx="172" cy="145" rx="4" ry="4\.4" fill="[^"]+"\/><circle cx="128" cy="145" r="1\.5"\/><circle cx="172" cy="145" r="1\.5"\/>/,eyeMarkup(p))
           .replace(/<path d="M150 147Q144 164 148 171Q153 175 158 171" fill="none" stroke="#875344" stroke-width="2\.5"\/>/,noseMarkup(p))
           .replace(/<path d="M134 184Q150 190 166 184" fill="none" stroke="#704038" stroke-width="3" stroke-linecap="round"\/>/,mouthMarkup(p));
    out=out.replace(/<g data-ebl-chain=\"v(?:64|67)\"[\s\S]*?<\/g>/g,'');
    const extras=compressionSleeveMarkup(p)+bodyBuildMarkup(p)+chainMarkup(p)+hairUnderCap(p)+hairSilhouetteFinish(p)+facePolish(p)+expressionFinish(p)+facialHair(p)+beardSurfaceFinish(p)+eyeBlack(p)+eyewear(p);
    if(extras){
      if(/<path data-ebl-cap-crown=/.test(out))out=out.replace(/(<path data-ebl-cap-crown=)/,extras+'$1');
      else out=out.replace(/<\/svg>/,extras+'</svg>');
    }
    return out;
  }
  function unified(raw={},size='md',action='portrait'){
    const p=productionModel(raw||{});
    // Suppress every older facial-hair layer at the source. The final compositor below
    // is the only facial-hair authority, which keeps thumbnails/live/saved players identical.
    const clean={...p,facial_hair_id:1,appearance_json:{facial_hair_id:1},appearance:{...((p.appearance&&typeof p.appearance==='object')?p.appearance:{}),facial_hair_id:1},avatar:{...((p.avatar&&typeof p.avatar==='object')?p.avatar:{}),facial_hair_id:1}};
    const html=baseRenderer(clean,size,action);
    return finalAppearancePass(html,p,action);
  }
  unified._eblUnifiedAppearance=true;
  window.eblUnifiedAppearanceRenderer=unified;
  window.eblPlayerArt=unified;
  window.eblPublicPortrait=(raw={},size='lg')=>unified(raw,size,'portrait');
  window.eblAvatarHtml=function(raw,size='card'){const map={mini:'xs',sm:'sm',card:'md',hero:'lg',lg:'lg'};return unified(raw,map[size]||'md','portrait')};
  window.playerPortraitMarkup=function(raw,pose='auto'){
    const p=productionModel(raw||{}),action=(pose&&pose!=='auto'&&pose!=='portrait')?pose:'portrait';
    let logo='';try{const spec=typeof window.eblUniformSpec==='function'?window.eblUniformSpec(p,'lg'):null;logo=spec?.secondaryLogo||(p.franchise_id&&typeof window.teamLogoUrl==='function'?window.teamLogoUrl(p.franchise_id,'secondary'):'')}catch(_){ }
    return `<div class="playerPortrait canonicalPlayerPortrait playerPortraitTeamBrandGameDay eblPortrait160" data-pos="#${Number(p.jersey_number??24)} • ${esc(p.primary_pos||'EBL')}">${logo?`<div class="playerPortraitTeamBackdropGameDay"><img src="${esc(logo)}" alt=""></div>`:''}${unified(p,'lg',action)}<span class="eblPortraitCorner160" aria-hidden="true">EBL</span><span class="eblPortraitStitch160" aria-hidden="true"></span></div>`;
  };
  window.eblIdentityMini=function(raw={},subtitle=''){
    const p=productionModel(raw),sub=subtitle||[p.primary_pos,p.jersey_number!=null?`#${p.jersey_number}`:''].filter(Boolean).join(' • ');
    return `<span class="eblIdentityMini"><span class="eblIdentityMini_art">${unified(p,'sm','portrait')}</span><span class="eblIdentityMini_copy"><b>${esc(p.name||p.player_name||'Player')}</b><small>${esc(sub)}</small></span></span>`;
  };
  window.eblPlayerByline=function(raw={},opts={}){
    const p=productionModel(raw),sub=opts.subtitle||opts.sub||[p.primary_pos,p.jersey_number!=null?`#${p.jersey_number}`:''].filter(Boolean).join(' • ');
    return `<span class="eblPlayerByline">${unified(p,opts.size||'sm',opts.action||'portrait')}<span class="eblPlayerByline_copy"><strong>${esc(p.name||p.player_name||'Player')}</strong>${sub?`<span>${esc(sub)}</span>`:''}</span></span>`;
  };

  window.eblCreatorFeatureThumb=function(extra={}){
    let focus='featureThumbFace';
    if(Object.prototype.hasOwnProperty.call(extra,'body_build_id'))focus='featureThumbBody';
    else if(Object.prototype.hasOwnProperty.call(extra,'hair_id'))focus='featureThumbHair';
    else if(Object.prototype.hasOwnProperty.call(extra,'facial_hair_id'))focus='featureThumbFacial';
    else if(Object.prototype.hasOwnProperty.call(extra,'eye_shape_id'))focus='featureThumbEyes';
    else if(Object.prototype.hasOwnProperty.call(extra,'nose_id'))focus='featureThumbNose';
    else if(Object.prototype.hasOwnProperty.call(extra,'mouth_id'))focus='featureThumbMouth';
    else if(Object.prototype.hasOwnProperty.call(extra,'ear_size_id'))focus='featureThumbEars';
    return `<div class="faceThumb faceThumbUnified ${focus}">${unified(creatorModel(extra),'sm','portrait')}</div>`;
  };
  window.faceThumbMarkup=function(f,hairId=1,facialId=N(creatorState().facial_hair_id,1),eyeColor){
    const faces=typeof FACE_PRESETS!=='undefined'?FACE_PRESETS:[];let faceId=faces.indexOf(f)+1;if(faceId<1)faceId=N(f?.id,1);
    const extra={face_id:faceId,hair_id:N(hairId,1),facial_hair_id:N(facialId,1)};
    if(eyeColor&&typeof EYE_COLORS!=='undefined'){const ix=EYE_COLORS.findIndex(x=>String(x.color).toLowerCase()===String(eyeColor).toLowerCase());if(ix>=0)extra.eye_color_id=ix+1}
    return `<div class="faceThumb faceThumbUnified featureThumbFace">${unified(creatorModel(extra),'sm','portrait')}</div>`;
  };
  window.renderCreator3D=function(hostId='creator3dPreview',source){
    const host=document.getElementById(hostId);if(!host)return;
    const p=creatorModel(source&&typeof source==='object'?source:{});
    host.classList.add('eblAvatarHost','creatorCanonicalCurrent');
    host.innerHTML=`<div class="avatar3dBadge">EBL PLAYER</div>${unified(p,'lg','portrait')}`;
  };
  function repaint(){try{if(typeof window.creatorAppearance==='function')window.creatorAppearance()}catch(e){console.warn('current creator repaint',e)}}
  window.pickFace=id=>{CREATOR.face_id=Math.max(1,Math.min(5,N(id,1)));repaint()};
  window.pickSkinTone=id=>{CREATOR.skin_color_id=Math.max(1,Math.min(8,N(id,1)));repaint()};
  window.pickHair=id=>{CREATOR.hair_id=Math.max(1,Math.min(8,N(id,1)));repaint()};
  window.pickHairColor=id=>{CREATOR.hair_color_id=Math.max(1,Math.min(9,N(id,3)));repaint()};
  window.pickFacialHair=id=>{const allowed=[1,2,3,5,4,6,7,8,11,12,13,10,14],q=N(id,1);CREATOR.facial_hair_id=allowed.includes(q)?q:1;repaint()};
  window.pickEyeColor=id=>{CREATOR.eye_color_id=Math.max(1,Math.min(6,N(id,6)));repaint()};
  window.pickNose=id=>{CREATOR.nose_id=Math.max(1,Math.min(6,N(id,1)));repaint()};
  window.pickEyeShape=id=>{CREATOR.eye_shape_id=Math.max(1,Math.min(6,N(id,1)));repaint()};
  window.pickMouth=id=>{CREATOR.mouth_id=Math.max(1,Math.min(6,N(id,1)));repaint()};
  window.pickEarSize=id=>{CREATOR.ear_size_id=Math.max(1,Math.min(4,N(id,2)));repaint()};
  window.pickEyeBlack=id=>{CREATOR.eye_black_id=Math.max(1,Math.min(5,N(id,1)));repaint()};
  window.pickEyewear=id=>{CREATOR.eyewear_id=Math.max(1,Math.min(5,N(id,1)));repaint()};
  window.pickChain=id=>{CREATOR.chain_id=Math.max(1,Math.min(7,N(id,1)));repaint()};
  window.pickSleeve=id=>{CREATOR.sleeve_id=Math.max(1,Math.min(4,N(id,1)));repaint()};
  window.pickBodyBuild=id=>{CREATOR.body_build_id=Math.max(1,Math.min(3,N(id,1)));repaint()};
  window.EBL_UNIFIED_APPEARANCE=Object.freeze({version:'rc160',publicRenderer:'eblPlayerArt',creatorState:'CREATOR',creatorPreview:'same renderer as saved players',mediumHair:'visible under cap',longHair:'eight sculpted under-cap silhouettes including curl, braid and long-hair surface detail',facialHair:'single final compositor with thirteen choices + natural asymmetric stroke-based stubble + connected/full beard geometry',faceDetails:['six noses','six eye shapes','six mouths','four ear sizes'],eyeBlack:'five choices including triangle and cross',bodyBuilds:['normal','heavy','muscular'],faceTuning:{oval:'fuller while still long',angular:'angled jaw with clearly flattened chin',brows:'six distinct sets linked to existing eye shape',complexion:'skin-aware facial outlines and cheek shading',expressions:'six saved mouth shapes with matching smile and focus details'},accessories:['five eyewear styles','gold/silver single-double-large chains','sleeves'],teamBranding:'preserved through current/current'});
  try{if(document.getElementById('creatorStage')&&typeof window.creatorAppearance==='function')window.creatorAppearance()}catch(_){ }
})();
