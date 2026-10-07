import os,time
from playwright.sync_api import sync_playwright
S=os.path.dirname(os.path.abspath(__file__)); os.makedirs(S+'/frames',exist_ok=True)
with sync_playwright() as p:
    b=p.chromium.launch(executable_path='/opt/pw-browsers/chromium',
                        args=['--force-device-scale-factor=1'])
    pg=b.new_page(viewport={'width':1920,'height':1080})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e)[:120]))
    pg.goto('http://127.0.0.1:8802/reel2.html')
    pg.wait_for_function('window.READY===true',timeout=25000)
    m=pg.evaluate('window.META'); n=m['FRAMES']
    print('frames',n,'errors',errs[:2],flush=True)
    cv=pg.locator('#c'); t0=time.time()
    for i in range(n):
        pg.evaluate('seek(%f)'%(i/m['FPS']))
        cv.screenshot(path='%s/frames/f%04d.png'%(S,i))
        if i%200==0: print(' ',i,'%.0fs'%(time.time()-t0),flush=True)
    print('done %.0fs'%(time.time()-t0),'errors',errs[:3])
    b.close()
