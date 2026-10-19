"""Check real encode/decode behavior of the PR and the proposed software correction.
Run from a checkout after exporting the baseline helper as described in README.md.
"""
import subprocess, pathlib, json, re, argparse
from fractions import Fraction
parser=argparse.ArgumentParser(); parser.add_argument('--ffmpeg-dir', default=''); parser.add_argument('--label', default=''); args=parser.parse_args()
V=pathlib.Path(__file__).resolve().parent; W=V.parents[1]; E=V/('output'+args.label); E.mkdir(exist_ok=True)
path='MediaBrowser.Controller/MediaEncoding/EncodingHelper.cs'
sources={'before':(V/'before-EncodingHelper.cs').read_text(), 'after':(W/path).read_text()}
recipes={v:dict(re.findall(r'Video3DFormat\.(\w+) => "([^"]+)"',s)) for v,s in sources.items()}
records=[]; commands=[]; tool_dir=args.ffmpeg_dir
def run(args,name):
 args=list(map(str,args))
 if args[0] in ('ffmpeg','ffprobe') and tool_dir: args[0]=str(pathlib.Path(tool_dir)/args[0])
 commands.append(args)
 p=subprocess.run(args,capture_output=True,timeout=120)
 (E/(name+'.log')).write_bytes(p.stderr)
 assert p.returncode==0,(name,p.stderr.decode()); return p.stdout

def probe(p,n):
 raw=run(['ffprobe','-v','error','-show_frames','-show_streams','-of','json',p],n+'-probe'); (E/(n+'.json')).write_bytes(raw); return json.loads(raw)
for kind in ['FullSideBySide','HalfSideBySide','FullTopAndBottom','HalfTopAndBottom']:
 horizontal='SideBySide' in kind; typ=3 if horizontal else 4
 for sar in ['1/1','4/3']:
  n=kind+'-'+sar.replace('/','_'); inp=E/(n+'.mp4')
  size='160x240' if horizontal else '320x120'; stack='hstack' if horizontal else 'vstack'
  fixture=f'color=c=red:s={size}:r=2[left];color=c=blue:s={size}:r=2[right];[left][right]{stack},setsar={sar}'
  run(['ffmpeg','-y','-v','error','-f','lavfi','-i',fixture,'-frames:v','2','-c:v','libx264','-preset','ultrafast','-x264-params',f'frame-packing={typ}',inp],n+'-input')
  assert any(sd['side_data_type']=='Stereo 3D' for sd in probe(inp,n)['frames'][0]['side_data_list'])
  for version in ['before','after']:
   name=n+'-'+version; out=E/(name+'.mp4')
   run(['ffmpeg','-y','-v','error','-i',inp,'-map_metadata','-1','-vf',recipes[version][kind],'-c:v','libx264','-preset','ultrafast',out],name+'-encode')
   result=probe(out,name); frames=result['frames']; assert len(frames)==2
   f=frames[0]; stereo=any(sd['side_data_type']=='Stereo 3D' for fr in frames for sd in fr.get('side_data_list',[]))
   expected_size=(160,240) if kind=='FullSideBySide' else (320,120) if kind=='FullTopAndBottom' else (320,240)
   assert (f['width'],f['height'])==expected_size
   sample_aspect=Fraction(f['sample_aspect_ratio'].replace(':','/'))
   rgb=run(['ffmpeg','-v','error','-i',out,'-frames:v','1','-pix_fmt','rgb24','-f','rawvideo','-'],name+'-pixels')
   channels=[sum(rgb[i::3])/len(rgb[i::3]) for i in range(3)]
   assert channels[0]>240 and max(channels[1:])<10,(name,channels)
   if version=='after': assert not stereo and sample_aspect==Fraction(sar),(name,stereo,sample_aspect)
   else:
    assert stereo
    assert sample_aspect==(1 if kind.startswith('Half') else Fraction(sar))
   records.append(dict(case=name,size=expected_size,sar=str(sample_aspect),stereo=stereo,mean_rgb=channels,filter=recipes[version][kind]))
# Plain mono is unaffected; packet-copy stereo retains its signalling.
mono=E/'mono.mp4'
run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=320x240:r=2,setsar=4/3','-frames:v','2','-c:v','libx264',mono],'mono')
f=probe(mono,'mono')['frames'][0]; assert f['sample_aspect_ratio']=='4:3' and (f['width'],f['height'])==(320,240)
assert not any(sd['side_data_type']=='Stereo 3D' for sd in f.get('side_data_list',[]))
copy=E/'copied.mp4'; run(['ffmpeg','-y','-v','error','-i',inp,'-c:v','copy',copy],'copy')
assert any(sd['side_data_type']=='Stereo 3D' for sd in probe(copy,'copy')['frames'][0]['side_data_list'])
(E/'results.json').write_text(json.dumps(records,indent=2)+'\n'); (E/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
print('PASS: eight before/after geometry, SAR, decoded-eye pixel and stereo-signalling cases; mono and copy controls')
