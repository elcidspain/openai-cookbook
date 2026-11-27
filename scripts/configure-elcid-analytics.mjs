import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
export function configureElcidAnalytics(source,configuredId=''){
 const id=String(configuredId).trim();
 if(id&&(!/^G-[A-Z0-9]{6,12}$/.test(id)||id==='G-T57TZW9QVK'))throw new Error('ELCID_GA_MEASUREMENT_ID must be EL CID verified independent web stream');
 const marker="const GA = '';";
 if(source.split(marker).length!==2)throw new Error('Missing EL CID analytics marker');
 return source.replace(marker,'const GA = '+JSON.stringify(id)+';');
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
 const path=resolve('elcid-site/site.js');
 writeFileSync(path,configureElcidAnalytics(readFileSync(path,'utf8'),process.env.ELCID_GA_MEASUREMENT_ID));
 console.log('EL CID optional analytics: '+(process.env.ELCID_GA_MEASUREMENT_ID?'configured':'disabled; no independent stream'));
}
