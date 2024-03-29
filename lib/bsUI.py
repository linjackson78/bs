import bs
import bsInternal
import os
import bsUtils
import random
import bsSpaz
import copy
import bsMap
import math
import bsCoopGame
import time
import bsAchievement
import weakref
import bsServerData
import threading
import bsGame

uiGlobals = {'mainMenuWindow':None}

gWindowStates = {}

quitWindowID = None

# we include this extra hash with shared input-mapping names
# so that we don't share mappings between differently-configured systems
# for instance, it looks like OUYA will give different keycodes for some gamepads
# than vanilla android will so we want to store their configs distinctly
gInputMapHash = None

gGameTypeSelection = 'Co-op Games'

gTitleColor = (0.72,0.7,0.75)
gHeadingColor = (0.72,0.7,0.75)
gInfoTextColor=(0.7,0.9,0.7)
gDidMenuIntro = False
gIconSelectColor = (0.4,0.3,1)

gUntestedGamePads = []
gCanAskToConfigGamePads = True
gShouldAskToMakeProfile = False

env = bs.getEnvironment()
gSmallUI = env['interfaceType'] == 'phone'
gMedUI = env['interfaceType'] == 'tabletSmall'

# gDoAndroidNav = True if (env['platform'] == 'android' and env['subplatform'] == 'google') else False
gDoAndroidNav = True

if 0: # test android nav
    gDoAndroidNav = True
    with bs.Context('UI'): bs.pushCall(bs.Call(bs.screenMessage,'FORCING ANDROID NAV FOR TESTING',color=(1,0,1)))
if 0: # test small UI
    gSmallUI = True
    with bs.Context('UI'): bs.pushCall(bs.Call(bs.screenMessage,'FORCING SMALL UI FOR TESTING',color=(1,0,1)))
if 0: # test med ui
    gMedUI = True
    with bs.Context('UI'): bs.pushCall(bs.Call(bs.screenMessage,'FORCING MEDIUM UI FOR TESTING',color=(1,0,1)))

if env['debugBuild']:
    bsUtils.suppressDebugReports()
del env

def _getPrizeStrings(entry):

    try: range1 = entry['prizeRange1']
    except Exception: range1 = None
    try: range2 = entry['prizeRange2']
    except Exception: range2 = None
    try: range3 = entry['prizeRange3']
    except Exception: range3 = None
    
    try: prize1 = entry['prize1']
    except Exception: prize1 = None
    try: prize2 = entry['prize2']
    except Exception: prize2 = None
    try: prize3 = entry['prize3']
    except Exception: prize3 = None
    
    try: trophyType1 = entry['prizeTrophy1']
    except Exception: trophyType1 = None
    try: trophyType2 = entry['prizeTrophy2']
    except Exception: trophyType2 = None
    try: trophyType3 = entry['prizeTrophy3']
    except Exception: trophyType3 = None

    doingTrophies = True if (trophyType1 is not None or trophyType2 is not None or trophyType3 is not None) else False

    outVals = []
    
    for rng,prize,trophyType in ((range1,prize1,trophyType1),
                                 (range2,prize2,trophyType2),
                                 (range3,prize3,trophyType3)):
        pr='' if rng is None else ('#'+str(rng[0])) if (rng[0] == rng[1]) else ('#'+str(rng[0])+'-'+str(rng[1]))
        pv = ''
        if trophyType is not None:
            pv += bs.getSpecialChar('trophy'+str(trophyType))
        # if we've got trophies but not for this entry, throw some space in to compensate
        # so the ticket counts line up
        #elif trophyType is None and prize is not None and doingTrophies: pv += '     '
        if prize is not None:
            pv = bs.getSpecialChar('ticketBacking')+str(prize)+pv
        outVals.append(pr)
        outVals.append(pv)
    #print 'RETURNING',outVals
    return outVals
        

    
def getInputMapHash(inputDevice):
    global gInputMapHash
    # currently we just do a single hash of *all* inputs on android and thats it.. good enough.
    # (grabbing mappings for a specific device looks to be non-trivial)
    try:
        if gInputMapHash is None:
            if 'android' in bs.getEnvironment()['userAgentString']:
                import hashlib
                md5 = hashlib.md5()
                for d in ['/system/usr/keylayout','/data/usr/keylayout','/data/system/devices/keylayout']:
                    try:
                        if os.path.isdir(d):
                            for fName in os.listdir(d):
                                # this is usually volume keys and stuff; assume we can skip it?..(since it'll vary a lot across devices)
                                if fName == 'gpio-keys.kl': continue
                                f = open(d+'/'+fName)
                                md5.update(f.read())
                                f.close()
                    except Exception:
                        bs.printException('error in getInputMapHash inner loop')
                        
                gInputMapHash = md5.hexdigest()
            else: gInputMapHash = ''
        return gInputMapHash
    except Exception:
        bs.printException('Exception in getInputMapHash')
        return ''

def dismissWiiRemotesWindow():
    pass

def _configChanged(val):
    bs.writeConfig()
    bs.applySettings()


def configCheckBox(parent,name,position,size,displayName=None,scale=None,maxWidth=None,autoSelect=True,valueChangeCall=None):
    if displayName is None: displayName = name

    def _valueChanged(val):
        bs.getConfig()[name] = val

        if valueChangeCall is not None: valueChangeCall(val)
        
        # special case: clicking kick-idle-players repeatedly unlocks co-op levels
        if name == 'Kick Idle Players':
            global gKickIdlePlayersKickCount
            try: count = gKickIdlePlayersKickCount
            except Exception: count = 1
            count += 1
            if count == 11:
                try:
                    import bsCoopGame
                    #campaign = bsCoopGame.getCampaign('Default')
                    levels = bsCoopGame.getCampaign('Default').getLevels() + bsCoopGame.getCampaign('Easy').getLevels()
                    for level in levels: level.setComplete(True)
                    bs.screenMessage("CO-OP LEVELS UNLOCKED! (temporarily)",color=(0,1,0))
                    bs.playSound(bs.getSound('gunCocking'))
                    bs.playSound(bs.getSound('gong'))
                except Exception,e:
                    print 'error during co-op unlock:',e
                    bs.screenMessage("ERROR UNLOCKING CO-OP LEVELS",color=(1,0,0))
                count = 1;
            gKickIdlePlayersKickCount = count

        bs.applySettings()
        bs.writeConfig()

    return bs.checkBoxWidget(parent=parent,autoSelect=autoSelect,position=position,size=size,text=displayName,textColor=(0.8,0.8,0.8),
                             value=bsInternal._getSetting(name),onValueChangeCall=_valueChanged,scale=scale,maxWidth=maxWidth)
    

def _inc(ctrl,name,minVal,maxVal,increment,callback):
    val = float(bs.textWidget(query=ctrl))
    val += increment
    val = max(minVal,min(val,maxVal))
    bs.textWidget(edit=ctrl,text=str(round(val,2)))
    bs.getConfig()[name] = val
    if callback:
        callback(val)
    _configChanged(val)

    
def configTextBox(parent,name,position,type="string",minVal=0,maxVal=100,increment=1.0,callback=None,changeSound=True,xOffset=0,displayName=None,textScale=1.0):

    if displayName is None: displayName = name
    if type == "int": initStr = "str(int(bsInternal._getSetting(" + repr(name) + ")))"
    elif type == "float": initStr = "str(round(bsInternal._getSetting(" + repr(name) + "),2))"
    else: initStr = "str(bsInternal._getSetting(" + repr(name) + "))"
    t = bs.textWidget(parent=parent,position=position,size=(100,30),text=displayName,maxWidth=160+xOffset,
                      color=(0.8,0.8,0.8,1.0),hAlign="left",vAlign="center",scale=textScale)
    retVals = {}
    if type == 'string':
        raise Exception("fixme unimplemented");
    else:
        retVals['textWidget'] = t = bs.textWidget(parent=parent,position=(246+xOffset,position[1]),size=(60,28),editable=False,
                                                  color=(0.3,1.0,0.3,1.0),
                                                  hAlign="right",vAlign="center",
                                                  text=eval(initStr),padding=2)
        retVals['minusButton'] = b = bs.buttonWidget(parent=parent,position=(330+xOffset,position[1]),size=(28,28),label="-",autoSelect=True,
                                                     onActivateCall=bs.Call(_inc,t,name,minVal,maxVal,-increment,callback),repeat=True,enableSound=(changeSound is True))
        retVals['plusButton'] = b = bs.buttonWidget(parent=parent,position=(380+xOffset,position[1]),size=(28,28),label="+",autoSelect=True,
                                                    onActivateCall=bs.Call(_inc,t,name,minVal,maxVal,increment,callback),repeat=True,enableSound=(changeSound is True))
    return retVals


def _makeRadioGroup(checkBoxes,valueNames,value,valueChangeCall):
    """ link the provided checkBoxes together into a radio group """
    def _radioPress(checkString,otherCheckBoxes,value):
        if value == 1:
            valueChangeCall(checkString)
            for cb in otherCheckBoxes:
                bs.checkBoxWidget(edit=cb,value=0)
    for i,checkBox in enumerate(checkBoxes):
        bs.checkBoxWidget(edit=checkBox,value=(value==valueNames[i]),onValueChangeCall=bs.Call(_radioPress,valueNames[i],[c for c in checkBoxes if c != checkBox]),isRadioButton=True)


class Window(object):
    # def __init__(self):
    #     print 'Window()'

    #     # give every window an invisible button representing
    #     # the party icon in the corner; this allows us to access it
    #     # via controller while in the menu
    #     self._partyButton = bs.buttonWidget(size=(50,50),autoSelect=True,
    #                                         label='',position=(200,200))
        
    def getRootWidget(self):
        return self._rootWidget

class ContinueWindow(Window):

    # def __del__(self):
    #     print '~ContinueWindow()'
        
    def __init__(self,activity,cost,continueCall,cancelCall):

        self._activity = weakref.ref(activity)
        self._cost = cost
        self._continueCall = continueCall
        self._cancelCall = cancelCall

        self._startCount = self._count = 20
        self._width = 300
        self._height = 200
        self._transitioningOut = False
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),background=False,
                                              transition='inScale',scale=1.5)
        
                                              #scale=2.1 if gSmallUI else 1.5 if gMedUI else 1.0)

        #t = bs.getResource('continuePurchaseText').replace('${PRICE}',bs.getSpecialChar('ticket')+'25')
        t = bs.getResource('continuePurchaseText').split('${PRICE}')
        tLeft = t[0]
        tLeftWidth = bs.getStringWidth(tLeft)
        tPrice = bs.getSpecialChar('ticket')+str(self._cost)
        tPriceWidth = bs.getStringWidth(tPrice)
        tRight = t[-1]
        tRightWidth = bs.getStringWidth(tRight)
        widthTotalHalf = (tLeftWidth+tPriceWidth+tRightWidth)*0.5
        
        bs.textWidget(parent=self._rootWidget,text=tLeft,flatness=1.0,shadow=1.0,
                      position=(self._width*0.5-widthTotalHalf,self._height-30),size=(0,0),
                      hAlign='left',vAlign='center')
        
        bs.textWidget(parent=self._rootWidget,text=tPrice,flatness=1.0,shadow=1.0,color=(1,0.5,0),
                      position=(self._width*0.5-widthTotalHalf+tLeftWidth,self._height-30),size=(0,0),
                      hAlign='left',vAlign='center')

        bs.textWidget(parent=self._rootWidget,text=tRight,flatness=1.0,shadow=1.0,
                      position=(self._width*0.5-widthTotalHalf+tLeftWidth+tPriceWidth+5,self._height-30),size=(0,0),
                      hAlign='left',vAlign='center')

        self._ticketsTextBase = bs.getResource('getTicketsWindow.youHaveShortText',fallback='getTicketsWindow.youHaveText')
        self._ticketsText = bs.textWidget(parent=self._rootWidget,text='',flatness=1.0,color=(1,0.5,0),shadow=1.0,
                                          position=(self._width*0.5+widthTotalHalf,self._height-50),size=(0,0),
                                          scale=0.35,hAlign='right',vAlign='center')
        
        self._counterText = bs.textWidget(parent=self._rootWidget,text=str(self._count),color=(0.7,0.7,0.7),scale=1.2,
                                          position=(self._width*0.5,self._height-80),size=(0,0),big=True,
                                          flatness=1.0,shadow=1.0,hAlign='center',vAlign='center')
        
        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,label=bs.getResource('endText',fallback='cancelText'),
                                             position=(30,30),size=(120,50),enableSound=False,
                                             onActivateCall=self._onCancelPress)
        
        self._continueButton = bs.buttonWidget(parent=self._rootWidget,label=bs.getResource('continueText'),
                                               position=(self._width-130,30),size=(120,50),
                                               onActivateCall=self._onContinuePress)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton,startButton=self._continueButton,selectedChild=self._cancelButton)

        self._countingDown = True
        self._countdownTimer = bs.Timer(1000,bs.WeakCall(self._tick),repeat=True,timeType='real')
        self._tick()

        
    def _tick(self):

        # if our target activity is gone or has ended, go away
        a = self._activity()
        if a is None or a.hasEnded():
            self._onCancel()
            return
        
        if bsInternal._getAccountState() == 'SIGNED_IN':
            s = bs.getSpecialChar('ticket')+str(bsInternal._getAccountTicketCount())
        else:
            s = '?'
        bs.textWidget(edit=self._ticketsText,text=self._ticketsTextBase.replace('${COUNT}',s))

        if self._countingDown:
            self._count -= 1
            bs.playSound(bs.getSound('tick'))
            if self._count <= 0:
                self._onCancel()
            else:
                bs.textWidget(edit=self._counterText,text=str(self._count))

    def _onCancelPress(self):
        # disallow for first second
        if self._startCount-self._count < 2:
            bs.playSound(bs.getSound('error'))
        else:
            self._onCancel()
            
    def _onContinuePress(self):
        # disallow for first second
        if self._startCount-self._count < 2:
            bs.playSound(bs.getSound('error'))
        else:
            # if somehow we got signed out...
            if bsInternal._getAccountState() != 'SIGNED_IN':
                bs.screenMessage(bs.getResource('notSignedInText'),color=(1,0,0))
                bs.playSound(bs.getSound('error'))
                return
                
            # if it appears we don't have enough tickets, offer to buy more
            tickets = bsInternal._getAccountTicketCount()
            if tickets < self._cost:
                # FIXME - should we start the timer back up again after?..
                self._countingDown = False
                bs.textWidget(edit=self._counterText,text='')
                bs.playSound(bs.getSound('error'))
                showGetTicketsPrompt()
                return
            
            if not self._transitioningOut:
                bs.playSound(bs.getSound('swish'))
                self._transitioningOut = True
                bs.containerWidget(edit=self._rootWidget,transition='outScale')
                self._continueCall()

    def _onCancel(self):
        if not self._transitioningOut:
            bs.playSound(bs.getSound('swish'))
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            self._cancelCall()
        
        
class ConfirmWindow(Window):

    def __init__(self,text="Are you sure?",action=None,width=360,height=100,
                 cancelButton=True,cancelIsSelected=False,color=(1,1,1),textScale=1.0,
                 okText=None,cancelText=None,originWidget=None):
        if okText is None: okText = bs.getResource('okText')
        if cancelText is None: cancelText = bs.getResource('cancelText')
        height += 40
        if width < 360: width = 360
        self._action = action

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = None
            scaleOrigin = None
            transition = 'inRight'
        
        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scale=2.1 if gSmallUI else 1.5 if gMedUI else 1.0,
                                              scaleOriginStackOffset=scaleOrigin)

        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-5-(height-75)*0.5),size=(0,0),
                          hAlign="center",vAlign="center",text=text,scale=textScale,color=color,maxWidth=width*0.9,maxHeight=height-75)
        # t = bs.textWidget(parent=self._rootWidget,position=(padding,padding+47),size=(width-2*padding,height-2*padding),
        #                   hAlign="center",vAlign="center",text=text,scale=textScale,color=color,maxWidth=width*0.9,maxHeight=height)
        if cancelButton:
            cb = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(20,20),size=(150,50),label=cancelText,onActivateCall=self._cancel)
            bs.containerWidget(edit=self._rootWidget,cancelButton=b)
            okButtonH = width-175
        else:
            # if they dont want a cancel button, we still want back presses to be able to dismiss the window;
            # just wire it up to do the ok button
            okButtonH = width*0.5-75
            cb = None
        b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(okButtonH,20),size=(150,50),label=okText,onActivateCall=self._ok)

        # if they didnt want a cancel button, we still want to be able to hit cancel/back/etc to dismiss the window
        if not cancelButton:
            bs.containerWidget(edit=self._rootWidget,onCancelCall=b.activate)
        
        bs.containerWidget(edit=self._rootWidget,selectedChild=cb if cb is not None and cancelIsSelected else b,startButton=b)

    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight' if self._transitionOut is None else self._transitionOut)

    def _ok(self):
        if not self._rootWidget.exists(): return
        bs.containerWidget(edit=self._rootWidget,transition='outLeft' if self._transitionOut is None else self._transitionOut)
        if self._action is not None:
            self._action()


class QuitWindow(Window):

    def __init__(self,swish=False,back=False,originWidget=None):
        
        global quitWindowID
        self._back = back
        if quitWindowID is not None:
            quitWindowID.delete()
            quitWindowID = None
        if swish:
            bs.playSound(bs.getSound('swish'))
            
        self._rootWidget = quitWindowID = ConfirmWindow((bs.getResource('quitGameText') if 'Mac' in bs.getEnvironment()['userAgentString'] else bs.getResource('exitGameText')).replace('${APP_NAME}',bs.getResource('titleText')),
                                                        self._doFadeAndQuit,originWidget=originWidget).getRootWidget()

    def _doFadeAndQuit(self):
        bsInternal._fadeScreen(False,time=200,endCall=bs.Call(bs.quit,soft=True,back=self._back))
        bsInternal._lockAllInput()
        # unlock and fade back in shortly.. just in case something goes wrong
        # (or on android where quit just backs out of our activity and we may come back)
        bs.realTimer(300,bsInternal._unlockAllInput)
        #bs.realTimer(300,bs.Call(bsInternal._fadeScreen,True))

        
class DebugWindow(Window):

    def __init__(self,transition='inRight'):
        
        self._width = width = 580
        self._height = height = 350 if gSmallUI else 420 if gMedUI else 520

        self._scrollWidth = self._width - 100
        self._scrollHeight = self._height - 120

        self._subWidth = self._scrollWidth*0.95;
        self._subHeight = 520
        
        self._stressTestGameType = 'Random'
        self._stressTestPlaylist = '__default__'
        self._stressTestPlayerCount = 8
        self._stressTestRoundDuration = 30

        # bs.playSound(bs.getSound('gong'))

        R = bs.getResource('debugWindow')
        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scale=2.35 if gSmallUI else 1.55 if gMedUI else 1.0,
                                              stackOffset=(0,-30) if gSmallUI else (0,0))
        
        self._doneButton = b = bs.buttonWidget(parent=self._rootWidget,position=(40,height-67),size=(120,60),scale=0.8,
                                               autoSelect=True,label=bs.getResource('doneText'), onActivateCall=self._done)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(0,height-60),size=(width,30),
                          text=R.titleText,hAlign="center",color=gTitleColor,
                          vAlign="center",maxWidth=260)

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._scrollWidth,self._scrollHeight),
                                             highlight=False, position=((self._width-self._scrollWidth)*0.5,50))
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)
        
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),
                                                background=False)
        
        v = self._subHeight - 70
        buttonWidth = 300
        # b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),size=(buttonWidth,60),
        #                     label=R.unlockCoopText,onActivateCall=self._unlockPressed)
        # v -= 80
        b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),size=(buttonWidth,60),
                            autoSelect=True,label=R.runCPUBenchmarkText,onActivateCall=self._runCPUBenchmarkPressed)
        bs.widget(edit=b,upWidget=self._doneButton,leftWidget=self._doneButton)
        v -= 60

        b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),size=(buttonWidth,60),
                            autoSelect=True,label=R.runGPUBenchmarkText,onActivateCall=self._runGPUBenchmarkPressed)
        v -= 60

        b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),size=(buttonWidth,60),
                            autoSelect=True,label=R.runMediaReloadBenchmarkText,onActivateCall=self._runMediaReloadBenchmarkPressed)
        v -= 60
        
        t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v+22),size=(0,0),text=R.stressTestTitleText,
                          maxWidth=200,color=gHeadingColor,
                          scale=0.85,hAlign="center",vAlign="center")
        v -= 45

        xOffs = 165
        t = bs.textWidget(parent=self._subContainer,position=(xOffs-10,v+22),size=(0,0),text=R.stressTestPlaylistTypeText,
                          maxWidth=130,color=gHeadingColor,
                          scale=0.65,hAlign="right",vAlign="center")

        PopupMenu(parent=self._subContainer,position=(xOffs,v),width=150,
                  choices=['Random','Teams','Free-For-All'],
                  choicesDisplay=[bs.getResource(a) for a in ['randomText','playModes.teamsText','playModes.freeForAllText']],
                  currentChoice='Auto',onValueChangeCall=self._stressTestGameTypeSelected)
        v -= 46
        t = bs.textWidget(parent=self._subContainer,position=(xOffs-10,v+22),size=(0,0),text=R.stressTestPlaylistNameText,
                          maxWidth=130,color=gHeadingColor,
                          scale=0.65,hAlign="right",vAlign="center")
        self._stressTestPlaylistNameField = bs.textWidget(parent=self._subContainer,position=(xOffs+5,v-5),size=(250,46),
                                                          text=self._stressTestPlaylist,hAlign="left",
                                                          vAlign="center",
                                                          autoSelect=True,
                                                          color=(0.9,0.9,0.9,1.0),
                                                          description=R.stressTestPlaylistDescriptionText,
                                                          editable=True,padding=4)
        v -= 29
        xSub = 60
        
        # player count
        t = bs.textWidget(parent=self._subContainer,position=(xOffs-10,v),size=(0,0),text=R.stressTestPlayerCountText,
                          color=(0.8,0.8,0.8,1.0),hAlign="right",vAlign="center",scale=0.65,
                          maxWidth=130)
        self._stressTestPlayerCountText = bs.textWidget(parent=self._subContainer,position=(246-xSub,v-14),
                                                      size=(60,28),editable=False,
                                                      color=(0.3,1.0,0.3,1.0),hAlign="right",vAlign="center",
                                                      text=str(self._stressTestPlayerCount),
                          padding=2)
        b = bs.buttonWidget(parent=self._subContainer,position=(330-xSub,v-11),size=(28,28),label="-",
                            autoSelect=True,onActivateCall=bs.Call(self._stressTestPlayerCountDecrement),
                            repeat=True,enableSound=True)
        b = bs.buttonWidget(parent=self._subContainer,position=(380-xSub,v-11),size=(28,28),label="+",
                            autoSelect=True,onActivateCall=bs.Call(self._stressTestPlayerCountIncrement),
                            repeat=True,enableSound=True)


        v -= 42

        # round duration
        t = bs.textWidget(parent=self._subContainer,position=(xOffs-10,v),size=(0,0),text=R.stressTestRoundDurationText,
                          color=(0.8,0.8,0.8,1.0),hAlign="right",vAlign="center",scale=0.65,
                          maxWidth=130)
        self._stressTestRoundDurationText = bs.textWidget(parent=self._subContainer,position=(246-xSub,v-14),
                                                      size=(60,28),editable=False,
                                                          color=(0.3,1.0,0.3,1.0),hAlign="right",vAlign="center",
                                                          text=str(self._stressTestRoundDuration),
                          padding=2)
        b = bs.buttonWidget(parent=self._subContainer,position=(330-xSub,v-11),size=(28,28),label="-",
                            autoSelect=True,onActivateCall=bs.Call(self._stressTestRoundDurationDecrement),
                            repeat=True,enableSound=True)
        b = bs.buttonWidget(parent=self._subContainer,position=(380-xSub,v-11),size=(28,28),label="+",
                            autoSelect=True,onActivateCall=bs.Call(self._stressTestRoundDurationIncrement),
                            repeat=True,enableSound=True)


        v -= 82

        b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),size=(buttonWidth,60),
                            autoSelect=True,label=R.runStressTestText,onActivateCall=self._stressTestPressed)
        bs.widget(b,showBufferBottom=50)

    def _stressTestPlayerCountDecrement(self):
        self._stressTestPlayerCount = max(1,self._stressTestPlayerCount - 1)
        bs.textWidget(edit=self._stressTestPlayerCountText,text=str(self._stressTestPlayerCount))

    def _stressTestPlayerCountIncrement(self):
        self._stressTestPlayerCount = self._stressTestPlayerCount + 1
        bs.textWidget(edit=self._stressTestPlayerCountText,text=str(self._stressTestPlayerCount))

    def _stressTestRoundDurationDecrement(self):
        self._stressTestRoundDuration = max(10,self._stressTestRoundDuration - 10)
        bs.textWidget(edit=self._stressTestRoundDurationText,text=str(self._stressTestRoundDuration))

    def _stressTestRoundDurationIncrement(self):
        self._stressTestRoundDuration = self._stressTestRoundDuration + 10
        bs.textWidget(edit=self._stressTestRoundDurationText,text=str(self._stressTestRoundDuration))


    def _stressTestGameTypeSelected(self,gameType):
        self._stressTestGameType = gameType

    def _runCPUBenchmarkPressed(self):
        bsUtils.runCPUBenchmark()

    def _runGPUBenchmarkPressed(self):
        bsUtils.runGPUBenchmark()

    def _runMediaReloadBenchmarkPressed(self):
        bsUtils.runMediaReloadBenchmark()
        
    # def _unlockPressed(self):
    #     try:
    #         import bsCoopGame
    #         campaign = bsCoopGame.getCampaign('Default')
    #         levels = campaign.getLevels()
    #         for level in levels: campaign.completeLevel(level['name'])
    #         bs.screenMessage("CO-OP LEVELS UNLOCKED!",color=(0,1,0))
    #         bs.playSound(bs.getSound('gunCocking'))
    #     except Exception:
    #         bs.screenMessage("ERROR UNLOCKING CO-OP LEVELS",color=(1,0,0))

    def _stressTestPressed(self):
        bsUtils.runStressTest(playlistType=self._stressTestGameType,
                              playlistName=bs.textWidget(query=self._stressTestPlaylistNameField),
                              playerCount=self._stressTestPlayerCount,
                              roundDuration=self._stressTestRoundDuration)
        bs.containerWidget(edit=self._rootWidget,transition='outRight')

    def _done(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = AdvancedSettingsWindow(transition='inLeft').getRootWidget()


class CreditsWindow(Window):
    def __init__(self,originWidget=None):

        bsInternal._setAnalyticsScreen('Credits Window')
        
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
            transition = 'inRight'
        
        width = 670
        height = 398 if gSmallUI else 500

        self._R = R = bs.getResource('creditsWindow')
        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=2.0 if gSmallUI else 1.3 if gMedUI else 1.0,
                                              stackOffset=(0,-8) if gSmallUI else (0,0))

        b = bs.buttonWidget(parent=self._rootWidget,position=(40,height-(68 if gSmallUI else 62)),size=(140,60),scale=0.8,
                            label=bs.getResource('backText'),buttonType='back', onActivateCall=self._back)

        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(0,height-(59 if gSmallUI else 54)),size=(width,30),
                          text=R.titleText.replace('${APP_NAME}',bs.getResource('titleText')),hAlign="center",
                          color=gTitleColor,
                          maxWidth=330,vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',position=(40,height-(68 if gSmallUI else 62)+5),size=(60,48),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(110,height-(59 if gSmallUI else 54)))
            
        
        s = bs.scrollWidget(parent=self._rootWidget,position=(40,35),size=(width-80,height-100),captureArrows=True)

        def _formatNames(names,inset):
            s = ''
            spaceWidth = bs.getStringWidth(' '*10)/10.0 # measure a series since theres overlaps and stuff..
            spacing = 330
            c1 = inset
            c2 = c1+spacing
            c3 = c2+spacing
            #c4 = c3+spacing
            lineWidth = 0
            line = ''
            for name in names:
                # move to the next column (or row) and print
                if lineWidth > c3:
                    s += line+'\n'
                    line = ''
                    lineWidth = 0

                #if lineWidth > c3: target = c4
                if lineWidth > c2: target = c3
                elif lineWidth > c1: target = c2
                else: target = c1
                #print 'ADDING',(target-width)/spaceWidth,'TO GET TO',target
                spacing = ' '*int((target-lineWidth)/spaceWidth)
                line += spacing
                line += name.decode('utf-8')
                lineWidth = bs.getStringWidth(line)
            if line != '': s += line+'\n'
            return s

        soundAndMusic = self._R.songCreditText
        soundAndMusic = soundAndMusic.replace('${TITLE}',"'William Tell (Trumpet Entry)'")
        soundAndMusic = soundAndMusic.replace('${PERFORMER}','The Apollo Symphony Orchestra')
        soundAndMusic = soundAndMusic.replace('${PERFORMER}','The Apollo Symphony Orchestra')
        soundAndMusic = soundAndMusic.replace('${COMPOSER}','Gioacchino Rossini')
        soundAndMusic = soundAndMusic.replace('${ARRANGER}','Chris Worth')
        soundAndMusic = soundAndMusic.replace('${PUBLISHER}','BMI')
        soundAndMusic = soundAndMusic.replace('${SOURCE}','www.AudioSparx.com')
        spc = '     '
        soundAndMusic = spc+soundAndMusic.replace('\n','\n'+spc)
        # soundAndMusic = ("     'William Tell (Trumpet Entry)' Performed by The Apollo Symphony Orchestra\n"
        #                  "     Composed by Gioacchino Rossini, Arranged by Chris Worth, Published by BMI,\n"
        #                  "     courtesy of www.AudioSparx.com")
        names = ['HubOfTheUniverseProd', 'Jovica', 'LG', 'Leady', 'Percy Duke', 'PhreaKsAccount',
                                       'Pogotron', 'Rock Savage', 'anamorphosis', 'benboncan', 'cdrk', 'chipfork',
                                       'guitarguy1985', 'jascha', 'joedeshon', 'loofa', 'm_O_m', 'mich3d', 'sandyrb',
                                       'shakaharu', 'sirplus', 'stickman', 'thanvannispen', 'virotic', 'zimbot']
        names.sort(key=lambda x:x.lower())

        freesoundNames = _formatNames(names,90)

        translationNames = _formatNames(bsServerData.translationContributors,60)

        # eww - need to chop this up since we're passing our 65535 vertex limit for meshes..
        # ..should add support for 32 bit indices i suppose...
        creditsText1 = ('  '+self._R.codingGraphicsAudioText.replace('${NAME}','Eric Froemling')+'\n'
                       '\n'
                       '  '+self._R.additionalAudioArtIdeasText.replace('${NAME}','Raphael Suter')+'\n'
                       '\n'
                       '  '+self._R.soundAndMusicText+'\n'
                       '\n'
                       +soundAndMusic+'\n'
                       '\n'
                       '     '+self._R.publicDomainMusicViaText.replace('${NAME}','Musopen.com')+'\n'
                       '        '+self._R.thanksEspeciallyToText.replace('${NAME}','the US Army, Navy, and Marine Bands')+'\n'
                       '\n'
                       '     '+self._R.additionalMusicFromText.replace('${NAME}','The YouTube Audio Library')+'\n'
                       '\n'
                       '     '+self._R.soundsText.replace('${SOURCE}','Freesound.org')+'\n'
                       '\n'
                       +freesoundNames+'\n'
                       '\n')
        creditsText2 = ('  '+self._R.languageTranslationsText+'\n'
                       '\n'
                       +translationNames+'\n'
                       '  Holiday theme vector art by designed by Freepik\n'
                       '\n'
                       '  '+self._R.specialThanksText+'\n'
                       '\n'
                       '     Todd, Laura, and Robert Froemling\n'
                       '     '+self._R.allMyFamilyText.replace('\n','\n     ')+'\n'
                       '     '+self._R.whoeverInventedCoffeeText+'\n'
                       '\n'
                       '  '+self._R.legalText+'\n'
                       '\n'
                       '     '+self._R.softwareBasedOnText.replace('${NAME}','the Khronos Group')+'\n'
                       '\n'
                       '                                                             www.froemling.net\n')

        # creditsText = (translationNames.split('ZpeedTube')[1]+'\n'
        #                '\n'
        #                '  '+self._R.specialThanksText+'\n')
        # print 'CT IS',repr(creditsText)
                       
        # print 'PUT THIS BACK TOGETHER'


        txt = creditsText1
        txt2 = creditsText2
        #txt = txt.replace("${SOUND_AND_MUSIC}",soundAndMusic)
        #txt = txt.replace("${FREESOUND_NAMES}",freesoundNames)
        #txt = txt.replace("${TRANSLATION_NAMES}",translationNames)
        #txt = txt.replace("${LEGAL_STUFF}","     This software is based in part on the work of the Khronos Group.")

        scale = 0.55
        self._subWidth = width-80
        self._subHeight = (bs.getStringHeight(txt)+bs.getStringHeight(txt2))*scale + 40
        c = self._subContainer = bs.containerWidget(parent=s,size=(self._subWidth,self._subHeight),background=False,claimsLeftRight=False,claimsTab=False)

        t = bs.textWidget(parent=c,
                          padding=4,
                          color=(0.7,0.9,0.7,1.0),
                          scale=scale,
                          flatness=1.0,
                          size=(0,0),
                          position=(0,self._subHeight-20),
                          hAlign='left',
                          vAlign='top',
                          text=txt
                          )
        t = bs.textWidget(parent=c,
                          padding=4,
                          color=(0.7,0.9,0.7,1.0),
                          scale=scale,
                          flatness=1.0,
                          size=(0,0),
                          position=(0,self._subHeight-bs.getStringHeight(txt)*scale),
                          hAlign='left',
                          vAlign='top',
                          text=txt2
                          )

    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()


class HelpWindow(Window):

    def __init__(self,mainMenu=False,originWidget=None):

        bsInternal._setAnalyticsScreen('Help Window')
        
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
            transition = 'inRight'
        
        R = bs.getResource('helpWindow')
        self._mainMenu = mainMenu
        width = 750
        height = 460 if gSmallUI else 530 if gMedUI else 600

        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = False
        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=1.77 if gSmallUI else 1.25 if gMedUI else 1.0,
                                              stackOffset=(0,-30) if gSmallUI else (0,15) if gMedUI else (0,0))

        t = bs.textWidget(parent=self._rootWidget,position=(0,height-(54 if gSmallUI else 45)),size=(width,25),
                          text=R.titleText.replace('${APP_NAME}',bs.getResource('titleText')),color=gTitleColor,
                          hAlign="center",vAlign="top")

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(44,55 if gSmallUI else 55),simpleCullingV=100.0,
                                             size=(width-88,height-120+(5 if gSmallUI else 0)),captureArrows=True)
        bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)

        # ugly: create this last so it gets first dibs at touch events (since we have it close to the scroll widget)
        b = bs.buttonWidget(parent=self._rootWidget,position=(40+0 if gSmallUI else 70,
                                                              height-(59 if gSmallUI else 50)),size=(140,60),scale=0.7 if gSmallUI else 0.8,
                            label=bs.getResource('backText') if self._mainMenu else "Close",buttonType='back' if self._mainMenu else None,
                            extraTouchBorderScale=2.0,
                            onActivateCall=self._close)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        if self._mainMenu and gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,55),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(10+(90 if gSmallUI else 120),height - (52 if gSmallUI else 39)))
            

        
        interfaceType = bs.getEnvironment()['interfaceType']

        self._subWidth = 660
        self._subHeight = 1590 + R.someDaysExtraSpace + R.orPunchingSomethingExtraSpace
        
        c = self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),background=False,claimsLeftRight=False,claimsTab=False)

        spacing = 1.0

        h = self._subWidth*0.5
        v = self._subHeight-55

        logoTex = bs.getTexture('logo')
        iconBuffer = 1.1

        header = (0.7,1.0,0.7,1.0)
        header2 = (0.8,0.8,1.0,1.0)
        paragraph = (0.8,0.8,1.0,1.0)

        txt = R.welcomeText.replace('${APP_NAME}',bs.getResource('titleText'))
        txtScale = 1.4
        txtMaxWidth = 480
        t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,flatness=0.5,resScale=1.5,
                          text=txt,hAlign="center",color=header,vAlign="center",maxWidth=txtMaxWidth)
        txtWidth = min(txtMaxWidth,bs.getStringWidth(txt)*txtScale)
        
        iconSize = 70
        h2 = h - (txtWidth*0.5+iconSize*0.5*iconBuffer)
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v-0.45*iconSize),texture=logoTex)

        forceTest = False
        # forceTest = True
        # print 'FORCING TEST'
        env = bs.getEnvironment()
        if (env['platform'] == 'android' and env['subplatform'] == 'alibaba') or forceTest:
            v -= 120.0
            txt = ('\xe8\xbf\x99\xe6\x98\xaf\xe4\xb8\x80\xe4\xb8\xaa\xe5\x8f\xaf\xe4\xbb\xa5\xe5\x92\x8c\xe5\xae\xb6\xe4\xba\xba\xe6\x9c\x8b\xe5\x8f\x8b\xe4\xb8\x80\xe8\xb5\xb7\xe7\x8e\xa9\xe7\x9a\x84\xe6\xb8\xb8\xe6\x88\x8f,\xe5\x90\x8c\xe6\x97\xb6\xe6\x94\xaf\xe6\x8c\x81\xe8\x81\x94 \xe2\x80\xa8\xe7\xbd\x91\xe5\xaf\xb9\xe6\x88\x98\xe3\x80\x82\n'
                   '\xe5\xa6\x82\xe6\xb2\xa1\xe6\x9c\x89\xe6\xb8\xb8\xe6\x88\x8f\xe6\x89\x8b\xe6\x9f\x84,\xe5\x8f\xaf\xe4\xbb\xa5\xe4\xbd\xbf\xe7\x94\xa8\xe7\xa7\xbb\xe5\x8a\xa8\xe8\xae\xbe\xe5\xa4\x87\xe6\x89\xab\xe7\xa0\x81\xe4\xb8\x8b\xe8\xbd\xbd\xe2\x80\x9c\xe9\x98\xbf\xe9\x87\x8c\xc2\xa0TV\xc2\xa0\xe5\x8a\xa9\xe6\x89\x8b\xe2\x80\x9d\xe7\x94\xa8 \xe6\x9d\xa5\xe4\xbb\xa3\xe6\x9b\xbf\xe5\xa4\x96\xe8\xae\xbe\xe3\x80\x82\n'
                   '\xe6\x9c\x80\xe5\xa4\x9a\xe6\x94\xaf\xe6\x8c\x81\xe6\x8e\xa5\xe5\x85\xa5\xc2\xa08\xc2\xa0\xe4\xb8\xaa\xe5\xa4\x96\xe8\xae\xbe')
            bs.textWidget(parent=c, size=(0,0), hAlign='center', vAlign='center', maxWidth = self._subWidth * 0.9,
                          position=(self._subWidth*0.5, v-180), text=txt)
            bs.imageWidget(parent=c, position=(self._subWidth - 320, v-120), size=(200, 200),
                           texture=bs.getTexture('aliControllerQR'))
            bs.imageWidget(parent=c, position=(90, v-130), size=(210, 210),
                           texture=bs.getTexture('multiplayerExamples'))
            v -= 120.0

        else:
            v -= spacing * 50.0
            #txtScale = R.someDaysTextScale
            txtScale = 0.66
            txt = R.someDaysText
            t = bs.textWidget(parent=c, position=(h,v), size=(0,0), scale=1.2, maxWidth=self._subWidth*0.9,
                              text=txt, hAlign="center", color=paragraph, vAlign="center", flatness=1.0)
            v -= (spacing * 25.0 + R.someDaysExtraSpace)
            #txtScale = R.orPunchingSomethingTextScale
            txtScale = 0.66
            txt = R.orPunchingSomethingText
            t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,maxWidth=self._subWidth*0.9,
                              text=txt,hAlign="center",color=paragraph,vAlign="center",flatness=1.0)
            v -= (spacing * 27.0 + R.orPunchingSomethingExtraSpace)
            txtScale = 1.0
            txt = R.canHelpText.replace('${APP_NAME}',bs.getResource('titleText'))
            t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,flatness=1.0,
                              text=txt,hAlign="center",color=paragraph,vAlign="center")

            v -= spacing * 70.0
            #txtScale = R.toGetTheMostTextScale
            txtScale = 1.0
            txt = R.toGetTheMostText
            t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,maxWidth=self._subWidth*0.9,
                              text=txt,hAlign="center",color=header,vAlign="center",flatness=1.0)

            v -= spacing * 40.0
            txtScale = 0.74
            txt = R.friendsText
            h2 = h - 220
            t = bs.textWidget(parent=c,position=(h2,v),size=(0,0),scale=txtScale,maxWidth=100,
                              text=txt,hAlign="right",color=header,vAlign="center",flatness=1.0)

            txt = R.friendsGoodText.replace('${APP_NAME}',bs.getResource('titleText'))
            txtScale = 0.7
            t = bs.textWidget(parent=c,position=(h2+10,v+8),size=(0,0),scale=txtScale,maxWidth=500,
                              text=txt,hAlign="left",color=paragraph,flatness=1.0)

            env = bs.getEnvironment()

            v -= spacing * 45.0
            txt = R.devicesText if (env['vrMode']) else R.controllersText
            txtScale = 0.74
            h2 = h - 220
            t = bs.textWidget(parent=c,position=(h2,v),size=(0,0),scale=txtScale,maxWidth=100,
                              text=txt,hAlign="right",color=header,vAlign="center",flatness=1.0)

            txtScale = 0.7
            if not env['vrMode']: txt = R.controllersInfoText.replace('${APP_NAME}',bs.getResource('titleText')).replace('${REMOTE_APP_NAME}',bsUtils._getRemoteAppName())
            else: txt = R.devicesInfoText.replace('${APP_NAME}',bs.getResource('titleText'))

            t = bs.textWidget(parent=c,position=(h2+10,v+8),size=(0,0),scale=txtScale,
                              maxWidth=500,maxHeight=105,
                              text=txt,hAlign="left",color=paragraph,flatness=1.0)

        v -= spacing * 150.0

        txt = R.controlsText
        txtScale = 1.4
        txtMaxWidth = 480
        t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,flatness=0.5,
                          text=txt,hAlign="center",color=header,vAlign="center",resScale=1.5,
                          maxWidth=txtMaxWidth)
        txtWidth = min(txtMaxWidth,bs.getStringWidth(txt)*txtScale)
        iconSize = 70


        h2 = h - (txtWidth*0.5+iconSize*0.5*iconBuffer)
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v-0.45*iconSize),texture=logoTex)
        v -= spacing * 45.0
        txtScale = 0.7
        txt = R.controlsSubtitleText.replace('${APP_NAME}',bs.getResource('titleText'))
        t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,maxWidth=self._subWidth*0.9,
                          flatness=1.0,text=txt,hAlign="center",color=paragraph,vAlign="center")
        v -= spacing * 160.0

        sep = 70
        iconSize = 100
        iconSize2 = 30
        icon2Offs = 55
        icon2Offs2 = 40

        # to determine whether to show ouya buttons here lets look for actual OUYA hardware
        # (we could be an ouya build running on other hardware)
        ouya = bsInternal._isRunningOnOuya();
        
        h2 = h - sep
        v2 = v
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v2-0.5*iconSize),
                           texture=bs.getTexture('buttonPunch'),color=(0.2,0.6,1) if ouya else (1,0.7,0.3))
        txtScale = R.punchInfoTextScale
        txt = R.punchInfoText
        t = bs.textWidget(parent=c,position=(h-sep-185+70,v+120),size=(0,0),scale=txtScale,flatness=1.0,
                          text=txt,hAlign="center",color=(0.3,0.65,1,1) if ouya else (1,0.7,0.3,1.0),vAlign="top")
        if ouya:
            bs.imageWidget(parent=c,size=(iconSize2,iconSize2),position=(h-sep-185+70-66,v+107),
                           texture=bs.getTexture('ouyaUButton'))
        h2 = h + sep
        v2 = v
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v2-0.5*iconSize),
                           texture=bs.getTexture('buttonBomb'),color=(1,0.3,0.3))
        txt = R.bombInfoText
        txtScale = R.bombInfoTextScale
        t = bs.textWidget(parent=c,position=(h+sep+50+60,v-35),size=(0,0),scale=txtScale,flatness=1.0,maxWidth=270,
                          text=txt,hAlign="center",color=(1,0.3,0.3,1.0),vAlign="top")
        if ouya:
            bs.imageWidget(parent=c,size=(iconSize2,iconSize2),position=(h+sep+50-5,v-48),
                           texture=bs.getTexture('ouyaAButton'))
        h2 = h
        v2 = v + sep
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v2-0.5*iconSize),
                           texture=bs.getTexture('buttonPickUp'),color=(1,0.8,0.3) if ouya else (0.5,0.5,1))
        txt = R.pickUpInfoText
        txtScale = R.pickUpInfoTextScale
        t = bs.textWidget(parent=c,position=(h+60+120,v+sep+50),size=(0,0),scale=txtScale,flatness=1.0,
                          text=txt,hAlign="center",color=(1,0.8,0.3,1) if ouya else (0.5,0.5,1,1.0),vAlign="top")
        if ouya:
            bs.imageWidget(parent=c,size=(iconSize2,iconSize2),position=(h+60+48,v+sep+38),
                           texture=bs.getTexture('ouyaYButton'))
        h2 = h
        v2 = v - sep
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v2-0.5*iconSize),
                           texture=bs.getTexture('buttonJump'),color=(0.4,1,0.4))
        txt = R.jumpInfoText
        txtScale = R.jumpInfoTextScale
        t = bs.textWidget(parent=c,position=(h-250+75,v-sep-15+30),size=(0,0),scale=txtScale,flatness=1.0,
                          text=txt,hAlign="center",color=(0.4,1,0.4,1.0),vAlign="top")
        if ouya:
            bs.imageWidget(parent=c,size=(iconSize2,iconSize2),position=(h-250+13,v-sep+3),
                           texture=bs.getTexture('ouyaOButton'))

        txt = R.runInfoText
        txtScale = R.runInfoTextScale
        t = bs.textWidget(parent=c,position=(h,v-sep-100),size=(0,0),scale=txtScale,maxWidth=self._subWidth*0.93,
                          flatness=1.0,text=txt,hAlign="center",color=(0.7,0.7,1.0,1.0),vAlign="center")

        v -= spacing * 280.0


        txt = R.powerupsText
        #txtScale = R.powerupsTextScale
        txtScale = 1.4
        txtMaxWidth = 480
        t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,flatness=0.5,
                          text=txt,hAlign="center",color=header,vAlign="center",maxWidth=txtMaxWidth)
        txtWidth = min(txtMaxWidth,bs.getStringWidth(txt)*txtScale)
        iconSize = 70
        h2 = h - (txtWidth*0.5+iconSize*0.5*iconBuffer)
        i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h2-0.5*iconSize,v-0.45*iconSize),texture=logoTex)

        v -= spacing * 50.0
        txtScale = R.powerupsSubtitleTextScale
        txt = R.powerupsSubtitleText
        t = bs.textWidget(parent=c,position=(h,v),size=(0,0),scale=txtScale,maxWidth=self._subWidth*0.9,
                          text=txt,hAlign="center",color=paragraph,vAlign="center",flatness=1.0)

        v -= spacing * 1.0

        m1 = -270
        m2 = -215
        m3 = 0
        iconSize = 50
        shadowSize = 80
        shadowOffsX = 3
        shadowOffsY = -4
        tBig = 1.1
        tSmall = 0.65

        shadowTex = bs.getTexture('shadowSharp')

        for tex in ['powerupPunch',
                    'powerupShield',
                    'powerupBomb',
                    'powerupHealth',
                    'powerupIceBombs',
                    'powerupImpactBombs',
                    'powerupStickyBombs',
                    'powerupLandMines',
                    'powerupCurse']:
            name = R[tex+'NameText']
            desc = R[tex+'DescriptionText']
            
            v -= spacing * 60.0

            i = bs.imageWidget(parent=c,size=(shadowSize,shadowSize),position=(h+m1+shadowOffsX-0.5*shadowSize,v+shadowOffsY-0.5*shadowSize),
                               texture=shadowTex,color=(0,0,0),opacity=0.5)
            i = bs.imageWidget(parent=c,size=(iconSize,iconSize),position=(h+m1-0.5*iconSize,v-0.5*iconSize),
                               texture=bs.getTexture(tex))

            txtScale = tBig
            txt = name
            t = bs.textWidget(parent=c,position=(h+m2,v+3),size=(0,0),scale=txtScale,maxWidth=200,flatness=1.0,
                              text=txt,hAlign="left",color=header2,vAlign="center")
            txtScale = tSmall
            txt = desc
            t = bs.textWidget(parent=c,position=(h+m3,v),size=(0,0),scale=txtScale,maxWidth=300,flatness=1.0,
                              text=txt,hAlign="left",color=paragraph,vAlign="center",resScale=0.5)

    def _close(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if self._mainMenu:
            uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = True


class ControllersWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):
        
        self._haveSelectedChild = False

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        R = bs.getResource('configControllersWindow')

        ua = bs.getEnvironment()['userAgentString']
        interfaceType = bs.getEnvironment()['interfaceType']
        #isOuya = bsInternal._isOuyaBuild()
        isOuya = bsInternal._isRunningOnOuya()
        isFantasia = bsInternal._isRunningOnFireTV()

        spacing = 50
        buttonWidth = 350

        width = 460
        height = 135

        spaceHeight = spacing*0.3


        showGamepads = False
        env = bs.getEnvironment()
        platform = env['platform']
        subplatform = env['subplatform']
        if platform == 'linux' or (platform == 'windows' and subplatform != 'oculus') or platform == 'android' or platform == 'mac':
            showGamepads = True
            height += spacing

        showTouch = False
        if bsInternal._haveTouchScreenInput():
            showTouch = True
            height += spacing

        showSpace1 = False
        if showGamepads or showTouch:
            showSpace1 = True
            height += spaceHeight

        showKeyboards = False
        if interfaceType == 'desktop':
            showKeyboards = True
            height += spacing*2

        showSpace2 = False
        if showKeyboards:
            showSpace2 = True
            height += spaceHeight

        showRemote = False
        if True:
            showRemote = True
            height += spacing

        showPS3 = False
        if 'Mac' in ua or isOuya:
            showPS3 = True
            height += spacing

        show360 = False
        if 'Mac' in ua or isOuya or isFantasia:
            show360 = True
            height += spacing

        showMacWiimote = False
        if 'Mac' in ua:
            showMacWiimote = True
            height += spacing

        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,scaleOriginStackOffset=scaleOrigin,
                                              scale=2.2 if gSmallUI else 1.5 if gMedUI else 1.0)
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(35,height-60),size=(140,65),scale=0.8,textScale=1.2,autoSelect=True,
                            label=bs.getResource('backText'),buttonType='back',onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        # need these vars to exist even if the buttons dont
        self._gamePadsButton = self._touchButton = self._keyboardButton = self._keyboard2Button = self._iDevicesButton = self._ps3Button = self._xbox360Button = self._wiimotesButton = -1

        t = bs.textWidget(parent=self._rootWidget,position=(0,height-49),size=(width,25),text=R.titleText,color=gTitleColor,
                          hAlign="center",vAlign="top")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(100,height-48))
        
        v = height - 75
        v -= spacing

        
        if showTouch:
            self._touchButton = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2,v),size=(buttonWidth,43),autoSelect=True,
            label=R.configureTouchText,onActivateCall=self._doTouchscreen)
            if not self._haveSelectedChild:
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._touchButton)
                bs.widget(edit=self._backButton,downWidget=self._touchButton)
                self._haveSelectedChild = True
            v -= spacing

        if showGamepads:
            self._gamePadsButton = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2-7,v),size=(buttonWidth,43),autoSelect=True,
                                                 label=R.configureControllersText,onActivateCall=self._doGamepads)
            if not self._haveSelectedChild:
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._gamePadsButton)
                bs.widget(edit=self._backButton,downWidget=self._gamePadsButton)
                self._haveSelectedChild = True
            v -= spacing
        else: self._gamePadsButton = None

        if showSpace1: v -= spaceHeight

        if showKeyboards:
            self._keyboardButton = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2+5,v),size=(buttonWidth,43),autoSelect=True,
                                label=R.configureKeyboardText,onActivateCall=self._configKeyboard)
            if not self._haveSelectedChild:
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._keyboardButton)
                bs.widget(edit=self._backButton,downWidget=self._keyboardButton)
                self._haveSelectedChild = True
            v -= spacing
            self._keyboard2Button = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2-3,v),size=(buttonWidth,43),autoSelect=True,
                                label=R.configureKeyboard2Text,onActivateCall=self._configKeyboard2)
            v -= spacing
        if showSpace2: v -= spaceHeight
        if showRemote:
            self._iDevicesButton = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2-5,v),size=(buttonWidth,43),autoSelect=True,
                                label=R.configureMobileText,
                                onActivateCall=self._doMobileDevices)
            if not self._haveSelectedChild:
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._iDevicesButton)
                bs.widget(edit=self._backButton,downWidget=self._iDevicesButton)
                self._haveSelectedChild = True
            v -= spacing
        if showPS3:
            self._ps3Button = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2+5,v),size=(buttonWidth,43),autoSelect=True,
                                label=R.ps3Text,
                                onActivateCall=self._doPS3Controllers)
            v -= spacing
        if show360:
            self._xbox360Button = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2-1,v),size=(buttonWidth,43),autoSelect=True,
                                label=R.xbox360Text,
                                onActivateCall=self._do360Controllers)
            v -= spacing
        if showMacWiimote:
            self._wiimotesButton = b = bs.buttonWidget(parent=self._rootWidget,position=((width-buttonWidth)/2+5,v),size=(buttonWidth,43),autoSelect=True,
                                label=R.wiimotesText,
                                onActivateCall=self._doWiimotes)
            v -= spacing

        self._restoreState()

    def _configKeyboard(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConfigKeyboardWindow(bsInternal._getInputDevice('Keyboard','#1')).getRootWidget()

    def _configKeyboard2(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConfigKeyboardWindow(bsInternal._getInputDevice('Keyboard','#2')).getRootWidget()

    def _doMobileDevices(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConnectMobileDevicesWindow().getRootWidget()

    def _doPS3Controllers(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConnectPS3ControllersWindow().getRootWidget()

    def _do360Controllers(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = Connect360ControllersWindow().getRootWidget()

    def _doWiimotes(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConfigureWiiRemotesWindow().getRootWidget()

    def _doGamepads(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConfigGamePadWindow().getRootWidget()

    def _doTouchscreen(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConfigTouchscreenWindow().getRootWidget()

    def _saveState(self):
        sel = self._rootWidget.getSelectedChild()
        if sel == self._gamePadsButton: selName = 'GamePads'
        elif sel == self._touchButton: selName = 'Touch'
        elif sel == self._keyboardButton: selName = 'Keyboard'
        elif sel == self._keyboard2Button: selName = 'Keyboard2'
        elif sel == self._iDevicesButton: selName = 'iDevices'
        elif sel == self._ps3Button: selName = 'PS3'
        elif sel == self._xbox360Button: selName = 'xbox360'
        elif sel == self._wiimotesButton: selName = 'Wiimotes'
        else: selName = 'Back'
        gWindowStates[self.__class__.__name__] = selName

    def _restoreState(self):
        try: selName = gWindowStates[self.__class__.__name__]
        except Exception: selName = None
        if selName == 'GamePads': sel = self._gamePadsButton
        elif selName == 'Touch': sel = self._touchButton
        elif selName == 'Keyboard': sel = self._keyboardButton
        elif selName == 'Keyboard2': sel = self._keyboard2Button
        elif selName == 'iDevices': sel = self._iDevicesButton
        elif selName == 'PS3': sel = self._ps3Button
        elif selName == 'xbox360': sel = self._xbox360Button
        elif selName == 'Wiimotes': sel = self._wiimotesButton
        elif selName == 'Back': sel = self._backButton
        else: sel = self._gamePadsButton if self._gamePadsButton is not None else self._backButton
        bs.containerWidget(edit=self._rootWidget,selectedChild=sel)


    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow']=SettingsWindow(transition='inLeft').getRootWidget()


class PopupWindow(Window):

    def __init__(self,position,size,scale=1.0,offset=(0,0),bgColor=(0.35,0.55,0.15),focusPosition=(0,0),focusSize=None):
        if focusSize is None: focusSize = size

        # in vr mode we can't have windows going outside the screen...
        if bs.getEnvironment()['vrMode']:
            focusSize = size
            focusPosition = (0,0)

        width = focusSize[0]
        height = focusSize[1]
        
        # ok, we've been given a desired width, height, and scale;
        # we now need to ensure that we're all onscreen by scaling down if need be
        # and clamping it to the UI bounds
        bounds = bs.getUIBounds()
        edgeBuffer = 15
        boundsWidth = (bounds[1]-bounds[0]-edgeBuffer*2)
        boundsHeight = (bounds[3]-bounds[2]-edgeBuffer*2)

        finWidth = width * scale
        finHeight = height * scale
        if finWidth > boundsWidth:
            scale /= (finWidth/boundsWidth)
            finWidth = width * scale
            finHeight = height * scale
        if finHeight > boundsHeight:
            scale /= (finHeight/boundsHeight)
            finWidth = width * scale
            finHeight = height * scale
        
        xMin = bounds[0]+edgeBuffer+finWidth*0.5
        yMin = bounds[2]+edgeBuffer+finHeight*0.5
        xMax = bounds[1]-edgeBuffer-finWidth*0.5
        yMax = bounds[3]-edgeBuffer-finHeight*0.5
                
        xFin = min(max(xMin,position[0]+offset[0]),xMax)
        yFin = min(max(yMin,position[1]+offset[1]),yMax)

        # ok, we've calced a valid x/y position and a scale based on or focus area.
        # ..now calc the difference between the center of our focus area and the center
        # of our window to come up with the offset we'll need to plug in to the window
        xOffs = ((focusPosition[0]+focusSize[0]*0.5) - (size[0]*0.5)) * scale
        yOffs = ((focusPosition[1]+focusSize[1]*0.5) - (size[1]*0.5)) * scale
        
        self._rootWidget = bs.containerWidget(transition='inScale',scale=scale,
                                              size=size,
                                              stackOffset=(xFin-xOffs,yFin-yOffs),
                                              scaleOriginStackOffset=(position[0],position[1]),
                                              onOutsideClickCall=self.onPopupCancel,
                                              color=bgColor,
                                              onCancelCall=self.onPopupCancel)
    def onPopupCancel(self):
        pass
        
class ColorPicker(PopupWindow):

    """ pops up a ui to select from a set of colors.
    passes the color to the delegate's colorPickerSelectedColor() method """

    cRaw = bsUtils.getPlayerColors()
    if len(cRaw) != 16: raise Exception("expected 16 player colors")
    colors = [cRaw[0:4],
              cRaw[4:8],
              cRaw[8:12],
              cRaw[12:16]]

    def __init__(self,parent,position,initialColor=(1,1,1),delegate=None,scale=None,offset=(0,0)):
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        self._delegate = delegate
        self._transitioningOut = False


        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(210,210),scale=scale,
                             focusPosition=(10,10),focusSize=(190,190),
                             bgColor=(0.5,0.5,0.5),offset=offset)
        
        rows = []
        closestDist = 9999
        closest = (0,0)
        for y in range(4):
            row = []
            rows.append(row)
            for x in range(4):
                color = self.colors[y][x]
                dist = abs(color[0]-initialColor[0])+abs(color[1]-initialColor[1])+abs(color[2]-initialColor[2])
                if dist < closestDist:
                    closest = (x,y)
                    closestDist = dist
                b = bs.buttonWidget(parent=self._rootWidget,position=(22+45*x,155-45*y),
                                    size=(35,40),label='',buttonType='square',onActivateCall=bs.WeakCall(self._select,x,y),
                                    autoSelect=True,color=color,extraTouchBorderScale=0.0)
                row.append(b)
                
        bs.containerWidget(edit=self._rootWidget,selectedChild=rows[closest[1]][closest[0]])

    def _select(self,x,y):
        if self._delegate: self._delegate.colorPickerSelectedColor(self,self.colors[y][x])
        bs.realTimer(50,self._transitionOut)
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            if self._delegate is not None: self._delegate.colorPickerClosing(self)
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            
    def onPopupCancel(self):
        if not self._transitioningOut:
            bs.playSound(bs.getSound('swish'))
        self._transitionOut()

    
class PopupMenuWindow(PopupWindow):


    def __init__(self,position,choices,currentChoice,delegate=None,width=230,
                 maxWidth=None,scale=1.0,choicesDisabled=[],choicesDisplay=[],autoSelect=None):

        parent = None

        if maxWidth is None: maxWidth = width * 1.5
        
        self._transitioningOut = False
        self._choices = list(choices)
        self._choicesDisplay = list(choicesDisplay)
        self._currentChoice=currentChoice
        self._choicesDisabled = list(choicesDisabled)
        self._doneBuilding = False
        if len(choices) < 1: raise Exception("Must pass at least one choice")
        self._width = width
        self._scale = scale
        if len(choices) > 8:
            self._height = 280
            self._useScroll = True
        else:
            self._height = 20+len(choices)*33
            self._useScroll = False 
        self._delegate = None # dont want this stuff called just yet..

        # extend width to fit our longest string (or our max-width)
        for index,choice in enumerate(choices):
            if len(choicesDisplay) == len(choices): choiceDisplayName = choicesDisplay[index]
            else: choiceDisplayName = choice
            if self._useScroll:
                self._width = max(self._width,min(maxWidth,bs.getStringWidth(choiceDisplayName))+75)
            else:
                self._width = max(self._width,min(maxWidth,bs.getStringWidth(choiceDisplayName))+60)

        # init parent class - this will rescale and reposition things as needed and create our root widget
        PopupWindow.__init__(self,position,size=(self._width,self._height),scale=self._scale)


        if self._useScroll:
            self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(20,20),
                                                 highlight=False, color=(0.35,0.55,0.15),size=(self._width-40,self._height-40))
            self._columnWidget = bs.columnWidget(parent=self._scrollWidget)
        else:
            self._offsetWidget = bs.containerWidget(parent=self._rootWidget,position=(30,15),size=(self._width-40,self._height),background=False)
            self._columnWidget = bs.columnWidget(parent=self._offsetWidget)
        for index,choice in enumerate(choices):
            if len(choicesDisplay) == len(choices): choiceDisplayName = choicesDisplay[index]
            else: choiceDisplayName = choice
            inactive = (choice in self._choicesDisabled)
            w = bs.textWidget(parent=self._columnWidget,size=(self._width-40,28),
                              onSelectCall=bs.Call(self._select,index),
                              clickActivate=True,
                              color=(0.5,0.5,0.5,0.5) if inactive else ((0.5,1,0.5,1) if choice == self._currentChoice else (0.8,0.8,0.8,1.0)),
                              padding=0,
                              maxWidth=maxWidth,
                              text=choiceDisplayName,
                              onActivateCall=self._activate,
                              vAlign='center',selectable=False if inactive else True)
            if choice == self._currentChoice:
                bs.containerWidget(edit=self._columnWidget,selectedChild=w,visibleChild=w)

        self._delegate = weakref.ref(delegate) # ok from now on our delegate can be called
        self._doneBuilding = True

    def _select(self,index):
        if self._doneBuilding:
            self._currentChoice = self._choices[index]

    def _activate(self):
        bs.playSound(bs.getSound('swish'))
        bs.realTimer(50,self._transitionOut)
        delegate = self._getDelegate()
        if delegate is not None:
            # call this in a timer so it doesnt interfere with us killing our widgets and whatnot..
            bs.realTimer(0,bs.Call(delegate.popupMenuSelectedChoice,self,self._currentChoice))

    def _getDelegate(self):
        return None if self._delegate is None else self._delegate()
    
    def _transitionOut(self):
        if not self._rootWidget.exists():
            return
        if not self._transitioningOut:
            self._transitioningOut = True
            delegate = self._getDelegate()
            if delegate is not None:
                delegate.popupMenuClosing(self)
            bs.containerWidget(edit=self._rootWidget,transition='outScale')

    def onPopupCancel(self):
        if not self._transitioningOut:
            bs.playSound(bs.getSound('swish'))
        self._transitionOut()

class PopupMenu(object):
    def __init__(self,parent,position,choices,currentChoice=None,onValueChangeCall=None,openingCall=None,closingCall=None,width=230,maxWidth=None,scale=None,choicesDisabled=[],choicesDisplay=[],buttonSize=(160,50),autoSelect=True):
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        if currentChoice not in choices: currentChoice = None
        self._choices = list(choices)
        if len(choices) == 0: raise Exception("no choices given")
        self._choicesDisplay = list(choicesDisplay)
        self._choicesDisabled = list(choicesDisabled)
        self._width = width
        self._maxWidth = maxWidth
        self._scale = scale
        self._currentChoice = currentChoice if currentChoice is not None else self._choices[0]
        self._position = position
        self._parent = parent
        if len(choices) < 1: raise Exception("Must pass at least one choice")
        self._parent = parent
        self._buttonSize = buttonSize
        self._button = bs.buttonWidget(parent=self._parent,position=(self._position[0],self._position[1]),autoSelect=autoSelect,
                                       size=self._buttonSize,scale=1.0,label='',onActivateCall=bs.Call(bs.realTimer,0,self._makePopup))
        self._onValueChangeCall = None # dont wanna call it for initial set
        self._openingCall = openingCall
        self._autoSelect = autoSelect
        self._closingCall = closingCall
        self.setChoice(self._currentChoice)
        self._onValueChangeCall = onValueChangeCall
        self._windowWidget = None

    def _makePopup(self):
        if not self._button.exists(): return
        if self._openingCall: self._openingCall()
        self._windowWidget = PopupMenuWindow(position=self._button.getScreenSpaceCenter(),
                                             delegate=self,
                                             width=self._width,maxWidth=self._maxWidth,scale=self._scale,choices=self._choices,currentChoice=self._currentChoice,
                                             choicesDisabled=self._choicesDisabled,choicesDisplay=self._choicesDisplay,autoSelect=self._autoSelect).getRootWidget()
    def getButtonWidget(self):
        return self._button

    def getWindowWidget(self):
        return self._windowWidget

    def popupMenuSelectedChoice(self,popupWindow,choice):
        self.setChoice(choice)
        if self._onValueChangeCall: self._onValueChangeCall(choice)

    def popupMenuClosing(self,popupWindow):
        if self._button.exists():
            bs.containerWidget(edit=self._parent,selectedChild=self._button)
        self._windowWidget = None
        if self._closingCall: self._closingCall()

    def setChoice(self,choice):
        self._currentChoice = choice
        if len(self._choicesDisplay) == len(self._choices):
            displayName = self._choicesDisplay[self._choices.index(choice)]
        else: displayName = choice
        if self._button.exists():
            bs.buttonWidget(edit=self._button,label=displayName)

class PurchaseConfirmWindow(PopupWindow):
    def __init__(self,position=(0,0),scale=None,offset=(0,0)):
        self._width = 340
        self._height = 180
        self._transitioningOut = False
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,offset=offset)
        itemName = 'SOME ITEM'
        itemPrice= bs.getSpecialChar('ticket')+'123'
        purchaseText = bs.getResource('store.purchaseConfirmText')
        purchaseTextPre = purchaseText.split('${ITEM}')[0].strip()
        purchaseTextPost = purchaseText.split('${ITEM}')[-1].strip().replace('${PRICE}',itemPrice)
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.7),size=(0,0),hAlign='center',vAlign='center',
                          maxWidth=self._width*0.9,text=purchaseText.replace('${ITEM}',itemName),scale=1.0)
        
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')

    def _onCancel(self):
        self._transitionOut()
                
    def onPopupCancel(self):

        bs.playSound(bs.getSound('swish'))
        self._onCancel()
        

        
class TournamentEntryWindow(PopupWindow):

    def __init__(self,tournamentID,tournamentActivity=None,position=(0,0),delegate=None,scale=None,offset=(0,0),onCloseCall=None):

        bsInternal._setAnalyticsScreen('Tournament Entry Window')
        
        self._tournamentID = tournamentID
        self._tournamentInfo = gTournamentInfo[self._tournamentID]

        # set a few vars depending on the tourney fee
        self._fee = self._tournamentInfo['fee']
        self._allowAds = self._tournamentInfo['allowAds']
        
        if self._fee == 4:
            self._purchaseName = 'tournament_entry_4'
            self._purchasePriceName = 'price.tournament_entry_4'
        elif self._fee == 3:
            self._purchaseName = 'tournament_entry_3'
            self._purchasePriceName = 'price.tournament_entry_3'
        elif self._fee == 2:
            self._purchaseName = 'tournament_entry_2'
            self._purchasePriceName = 'price.tournament_entry_2'
        elif self._fee == 1:
            self._purchaseName = 'tournament_entry_1'
            self._purchasePriceName = 'price.tournament_entry_1'
        else:
            if self._fee != 0: raise Exception("invalid fee: "+str(self._fee))
            self._purchaseName = 'tournament_entry_0'
            self._purchasePriceName = 'price.tournament_entry_0'

        self._purchasePrice = None
        
        self._onCloseCall = onCloseCall
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        self._delegate = delegate
        self._transitioningOut = False

        self._tournamentActivity = tournamentActivity
        
        self._width = 340
        self._height = 220

        bgColor = (0.5,0.4,0.6)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor,offset=offset)

        self._lastAdPressTime = -9999
        self._lastTicketPressTime = -9999
        self._entering = False
        self._launched = False

        env = bs.getEnvironment()

        # show the ad button only if we support ads *and* it has a level 1 fee
        #self._doAdButton = (bsInternal._hasVideoAds() and self._tournamentInfo['fee'] == 1)
        self._doAdButton = (bsInternal._hasVideoAds() and self._allowAds)

        xOffs = 0 if self._doAdButton else 85

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(20,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancel,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-20),size=(0,0),hAlign='center',vAlign='center',
                                        scale=0.6,text=bs.getResource('tournamentEntryText'),maxWidth=200,color=(1,1,1,0.4))
        
        b = self._payWithTicketsButton = bs.buttonWidget(parent=self._rootWidget,position=(30+xOffs,60),autoSelect=True,
                                                         buttonType='square',size=(120,120),label='',
                                                         onActivateCall=self._onPayWithTicketsPress)
        self._ticketImagePosition = (50+xOffs,94)
        self._ticketImagePositionFree = (50+xOffs,80)
        self._ticketImage = bs.imageWidget(parent=self._rootWidget,drawController=b,size=(80,80),position=self._ticketImagePosition,texture=bs.getTexture('tickets'))
        self._ticketCostTextPosition = (87+xOffs,88)
        self._ticketCostTextPositionFree = (87+xOffs,120)
        self._ticketCostText = bs.textWidget(parent=self._rootWidget,drawController=b,position=self._ticketCostTextPosition,size=(0,0),hAlign='center',vAlign='center',
                                             scale=0.6,text='',
                                             maxWidth=95,color=(0,1,0))
        self._freePlaysRemainingText = bs.textWidget(parent=self._rootWidget,drawController=b,position=(87+xOffs,78),size=(0,0),hAlign='center',vAlign='center',
                                                     scale=0.33,text='',
                                                     maxWidth=95,color=(0,0.8,0))

        if self._doAdButton:

            b = self._payWithAdButton = bs.buttonWidget(parent=self._rootWidget,position=(190,60),autoSelect=True,
                                                    buttonType='square',size=(120,120),label='',
                                                    onActivateCall=self._onPayWithAdPress)
            self._payWithAdImage = bs.imageWidget(parent=self._rootWidget,drawController=b,size=(80,80),position=(210,94),texture=bs.getTexture('tv'))

            self._adTextPosition = (251,88)
            self._adTextPositionRemaining = (251,92)
            haveAdTriesRemaining = True if self._tournamentInfo['adTriesRemaining'] is not None else False
            self._adText = bs.textWidget(parent=self._rootWidget,drawController=b,position=self._adTextPositionRemaining if haveAdTriesRemaining else self._adTextPosition,size=(0,0),hAlign='center',vAlign='center',
                                         scale=0.6,text=bs.getResource('watchAVideoText',fallback='watchAnAdText'),
                                         maxWidth=95,color=(0,1,0))
            adPlaysRemainingText = '' if not haveAdTriesRemaining else ''+str(self._tournamentInfo['adTriesRemaining'])
            self._adPlaysRemainingText = bs.textWidget(parent=self._rootWidget,drawController=b,position=(251,78),size=(0,0),hAlign='center',vAlign='center',
                                                       scale=0.33,text=adPlaysRemainingText,
                                                       maxWidth=95,color=(0,0.8,0))


            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,120),size=(0,0),hAlign='center',vAlign='center',
                          scale=0.6,text=bs.getResource('orText').replace('${A}','').replace('${B}',''),maxWidth=35,color=(1,1,1,0.5))
        else:
            self._payWithAdButton = None


        # self._ticketCountText = bs.textWidget(parent=self._rootWidget,position=(self._width-215+100,33),size=(0,0),hAlign='right',vAlign='center',
        #                                       scale=0.65,maxWidth=100,color=(1,0.5,0))

        self._getTicketsButton = bs.buttonWidget(parent=self._rootWidget,position=(self._width-190+110,15),
                                                 autoSelect=True,scale=0.6,size=(120,60),
                                                 textColor=(1,0.6,0),
                                                 #label=bs.getResource('getTicketsWindow.titleText'),
                                                 label=bs.getSpecialChar('ticket'),
                                                 color=(0.6,0.4,0.7),
                                                 onActivateCall=self._onGetTicketsPress)

        self._secondsRemaining = None
        
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)

        # lets also ask the server for info about this tournament (time remaining, etc)
        # so we can show the user time remaining, disallow entry if time has run out/etc.
        self._timeRemainingText = bs.textWidget(parent=self._rootWidget,position=(70,23),size=(0,0),hAlign='center',vAlign='center',
                                                text='-',scale=0.65,maxWidth=100,flatness=1.0,color=(0.7,0.7,0.7))
        self._timeRemainingLabelText = bs.textWidget(parent=self._rootWidget,position=(70,40),size=(0,0),hAlign='center',vAlign='center',
                                                     text=bs.getResource('coopSelectWindow.timeRemainingText'),
                                                     scale=0.45,flatness=1.0,maxWidth=100,color=(0.7,0.7,0.7))

        self._lastQueryTime = None
        
        # if there seems to be a relatively-recent valid cached info for this tournament, use it.
        # ..otherwise we'll kick off a query ourselves.
        if self._tournamentID in gTournamentInfo and gTournamentInfo[self._tournamentID]['valid'] and (bs.getRealTime() - gTournamentInfo[self._tournamentID]['timeReceived'] < 1000*60*5):
            try:
                info = gTournamentInfo[self._tournamentID]
                self._secondsRemaining = max(0, info['timeRemaining'] - int((bs.getRealTime()-info['timeReceived'])/1000))
                self._haveValidData = True
                self._lastQueryTime = bs.getRealTime()
            except Exception:
                bs.printException("error using valid tourney data")
                self._haveValidData = False
        else:
            self._haveValidData = False
            
        self._fgState = bsUtils.gAppFGState
        
        self._runningQuery = False
        
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),repeat=True,timeType='real')
        self._update()
        
        self._restoreState()

    def _onTournamentQueryResponse(self,data):
        self._runningQuery = False
        if data is not None:
            data = data['t'] # this used to be the whole payload
            _cacheTournamentInfo(data)
            self._secondsRemaining = gTournamentInfo[self._tournamentID]['timeRemaining']
            self._haveValidData = True
        
    def _saveState(self):
        if not self._rootWidget.exists(): return
        sel = self._rootWidget.getSelectedChild()
        if sel == self._payWithAdButton: selName = 'Ad'
        else: selName = 'Tickets'
        bs.getConfig()['Tournament Pay Selection'] = selName
        bs.writeConfig()
    
    def _restoreState(self):
        try: selName = bs.getConfig()['Tournament Pay Selection']
        except Exception: selName = 'Tickets'
        if selName == 'Ad' and self._payWithAdButton is not None: sel = self._payWithAdButton
        else: sel = self._payWithTicketsButton
        bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
    
    def _update(self):
        
        # we may outlive our widgets..
        if not self._rootWidget.exists(): return
        
        # if we've been foregrounded/backgrounded we need to re-grab data
        if self._fgState != bsUtils.gAppFGState:
            self._fgState = bsUtils.gAppFGState
            self._haveValidData = False
            
        # if we need to run another tournament query, do so..
        if not self._runningQuery and ((self._lastQueryTime is None)
                                       or (not self._haveValidData)
                                       or (bs.getRealTime() - self._lastQueryTime > 30000)):
            bsInternal._tournamentQuery(args={'source':'entry window' if self._tournamentActivity is None else 'retry entry window'},
                                        callback=bs.WeakCall(self._onTournamentQueryResponse))
            self._lastQueryTime = bs.getRealTime()
            self._runningQuery = True
        
        # grab the latest info on our tourney
        self._tournamentInfo = gTournamentInfo[self._tournamentID]

        # if we dont have valid data always show a '-' for time
        if not self._haveValidData:
            bs.textWidget(edit=self._timeRemainingText,text='-')
        else:
            if self._secondsRemaining is not None:
                self._secondsRemaining = max(0,self._secondsRemaining - 1)
                bs.textWidget(edit=self._timeRemainingText,text=bsUtils.getTimeString(self._secondsRemaining*1000,centi=False))

        # keep price up-to-date and update the button with it..
        self._purchasePrice = bsInternal._getAccountMiscReadVal(self._purchasePriceName,None)
        
        bs.textWidget(edit=self._ticketCostText,
                      text=(bs.getResource('getTicketsWindow.freeText') if self._purchasePrice == 0 else bs.getResource('getTicketsWindow.ticketsText')
                            .replace('${COUNT}',str(self._purchasePrice) if self._purchasePrice is not None else '?')),
                      position=self._ticketCostTextPositionFree if self._purchasePrice == 0 else self._ticketCostTextPosition,
                      scale=1.0 if self._purchasePrice == 0 else 0.6)

        bs.textWidget(edit=self._freePlaysRemainingText,
                      text= '' if (self._tournamentInfo['freeTriesRemaining'] in [None,0] or self._purchasePrice != 0) else ''+str(self._tournamentInfo['freeTriesRemaining']))

        bs.imageWidget(edit=self._ticketImage,opacity=0.2 if self._purchasePrice == 0 else 1.0,
                       position=self._ticketImagePositionFree if self._purchasePrice == 0 else self._ticketImagePosition)

        if self._doAdButton:
            enabled = bsInternal._haveIncentivizedAd()
            haveAdTriesRemaining = True if (self._tournamentInfo['adTriesRemaining'] is not None and self._tournamentInfo['adTriesRemaining'] > 0) else False
            bs.textWidget(edit=self._adText,position=self._adTextPositionRemaining if haveAdTriesRemaining else self._adTextPosition,
                          color=(0,1,0) if enabled else (0.5,0.5,0.5))
            bs.imageWidget(edit=self._payWithAdImage,opacity=1.0 if enabled else 0.2)
            bs.buttonWidget(edit=self._payWithAdButton,color=(0.5,0.7,0.2) if enabled else (0.5,0.5,0.5))
            adPlaysRemainingText = '' if not haveAdTriesRemaining else ''+str(self._tournamentInfo['adTriesRemaining'])
            bs.textWidget(edit=self._adPlaysRemainingText,text=adPlaysRemainingText,color=(0,0.8,0) if enabled else (0.4,0.4,0.4))

            
        try: tStr = str(bsInternal._getAccountTicketCount())
        except Exception: tStr = '?'
        #bs.textWidget(edit=self._ticketCountText,text=bs.getSpecialChar('ticket')+tStr)
        bs.buttonWidget(edit=self._getTicketsButton,label=bs.getSpecialChar('ticket')+tStr)

        # if we've got no outstanding transactions and it looks like we've got a tournament-entry pass,
        # go ahead and enter it. Once our outstanding transactions are again clear we'll go ahead and start
        # if (not self._entering and not bsInternal._haveOutstandingTransactions()):
        #     pass
        
            # if we've entered via a ticket purchase:
            # if bsInternal._getPurchased(self._purchaseName):
            #     self._entering = True
            #     bsInternal._addTransaction({'type':'ENTER_TOURNAMENT',
            #                                 'fee':self._fee,
            #                                 'tournamentID':self._tournamentID})
            #     bsInternal._runTransactions()
                
            # if we've entered via an ad purchase:
            # if self._allowAds and bsInternal._getPurchased('tournament_entry_ad'):
            #     self._entering = True
            #     bsInternal._addTransaction({'type':'ENTER_TOURNAMENT',
            #                                 'fee':'ad',
            #                                 'tournamentID':self._tournamentID})
            #     bsInternal._runTransactions()

        # once the entry goes through, go ahead and start the game
        # if self._entering and not bsInternal._haveOutstandingTransactions() and not self._launched:
        #     self._launch()
            
        # make sure our transactions are going through as fast as possible..
        # bsInternal._runTransactions()

    def _launch(self):
        if self._launched: return
        self._launched = True

        launched = False

        # if they gave us an existing activity, just restart it..
        if self._tournamentActivity is not None:
            try:
                bs.realTimer(100, lambda: bs.playSound(bs.getSound('cashRegister')))
                with bs.Context(self._tournamentActivity): self._tournamentActivity.end({'outcome':'restart'},force=True)
                bs.realTimer(300, self._transitionOut)
                launched = True
                bs.screenMessage(bs.translate('serverResponses','Entering tournament...'),color=(0,1,0))
            # we can hit exeptions here if _tournamentActivity ends before our restart attempt happens
            # ..in this case we'll fall back to launching a new session.  This is not ideal since players will have to rejoin, etc.
            # ..but it works for now
            except Exception:
                pass

        # if we had no existing activity (or were unable to restart it) launch a new session.
        if not launched:
            bs.realTimer(100, lambda: bs.playSound(bs.getSound('cashRegister')))
            bs.realTimer(1000, lambda: bsUtils._handleRunChallengeGame(self._tournamentInfo['game'],args={'minPlayers':self._tournamentInfo['minPlayers'],
                                                                                                          'maxPlayers':self._tournamentInfo['maxPlayers'],
                                                                                                          'tournamentID':self._tournamentID}))
            bs.realTimer(700, self._transitionOut)
            bs.screenMessage(bs.translate('serverResponses','Entering tournament...'),color=(0,1,0))
        
    def _onPayWithTicketsPress(self):

        # if we're already entering, ignore..
        if self._entering: return

        if not self._haveValidData:
            bs.screenMessage(bs.getResource('tournamentCheckingStateText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
            
        # if we dont have a price..
        if self._purchasePrice is None:
            bs.screenMessage(bs.getResource('tournamentCheckingStateText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
        
        # deny if it looks like the tourney has ended
        if self._secondsRemaining == 0:
            bs.screenMessage(bs.getResource('tournamentEndedText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
        
        # deny if we don't have enough tickets
        try: ticketCount = bsInternal._getAccountTicketCount()
        except Exception: ticketCount = None
        ticketCost = self._purchasePrice
        if ticketCount is not None and ticketCost is not None and ticketCount < ticketCost:
            showGetTicketsPrompt()
            bs.playSound(bs.getSound('error'))
            return

        curTime = bs.getRealTime()
        #if curTime-self._lastTicketPressTime > 5000:
        self._lastTicketPressTime = curTime
        bsInternal._inGamePurchase(self._purchaseName,ticketCost)
        
        self._entering = True
        bsInternal._addTransaction({'type':'ENTER_TOURNAMENT',
                                    'fee':self._fee,
                                    'tournamentID':self._tournamentID})
        bsInternal._runTransactions()
        self._launch()
        
    def _onPayWithAdPress(self):
        
        # if we're already entering, ignore..
        if self._entering: return

        if not self._haveValidData:
            bs.screenMessage(bs.getResource('tournamentCheckingStateText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
        
        # deny if it looks like the tourney has ended
        if self._secondsRemaining == 0:
            bs.screenMessage(bs.getResource('tournamentEndedText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
        
        curTime = bs.getRealTime()
        if curTime-self._lastAdPressTime > 5000:
            self._lastAdPressTime = curTime
            bsUtils._showAd('tournament_entry',onCompletionCall=bs.WeakCall(self._onAdComplete),passActuallyShowed=True)

    def _onAdComplete(self,actuallyShowed):

        # if we're already entering, ignore..
        if self._entering: return

        if not actuallyShowed: return
        
        self._entering = True
        bsInternal._addTransaction({'type':'ENTER_TOURNAMENT',
                                    'fee':'ad',
                                    'tournamentID':self._tournamentID})
        bsInternal._runTransactions()
        self._launch()
        
    def _onGetTicketsPress(self):
        # if we're already entering, ignore presses..
        if self._entering: return
        
        GetTicketsWindow(modal=True,originWidget=self._getTicketsButton)

    def _onCancel(self):

        # don't allow canceling for several seconds after poking an enter button
        # if it looks like we're waiting on a purchase or entring the tournament
        #print 'HAVE OUTSTANDING?',bsInternal._haveOutstandingTransactions(),'PURCHASED?',bsInternal._getPurchased(self._purchaseName)
        if (bs.getRealTime() - self._lastTicketPressTime < 6000) and (bsInternal._haveOutstandingTransactions() or bsInternal._getPurchased(self._purchaseName) or self._entering):
            bs.playSound(bs.getSound('error'))
            return
        
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._rootWidget.exists(): return
        if not self._transitioningOut:
            self._transitioningOut = True
            self._saveState()
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            if self._onCloseCall is not None:
                self._onCloseCall()

    def onPopupCancel(self):

        bs.playSound(bs.getSound('swish'))
        self._onCancel()

class TournamentScoresWindow(PopupWindow):

    def __init__(self,tournamentID,tournamentActivity=None,position=(0,0),scale=None,offset=(0,0),
                 tintColor=(1,1,1),tint2Color=(1,1,1),selectedCharacter=None,onCloseCall=None):

        self._tournamentID = tournamentID
            
        self._onCloseCall = onCloseCall
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        self._transitioningOut = False
        
        self._width = 400
        self._height = 300 if gSmallUI else 370 if gMedUI else 450

        bgColor = (0.5,0.4,0.6)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor,offset=offset)

        env = bs.getEnvironment()

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-20),size=(0,0),hAlign='center',vAlign='center',
                                        scale=0.6,text=bs.getResource('tournamentStandingsText'),maxWidth=200,color=(1,1,1,0.4))

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._width-60,self._height-70),position=(30,30),
                                             highlight=False,simpleCullingV=10)
        bs.widget(edit=self._scrollWidget,autoSelect=True)

        self._loadingText = bs.textWidget(parent=self._scrollWidget,
                                          #position=(subWidth*0.1-10,subHeight-20-incr*i),
                                          #maxWidth=subWidth*0.1,
                                          scale=0.5,
                                          text=bs.getResource('loadingText')+'...',
                                          size=(self._width-60,100),
                                          hAlign='center',vAlign='center')
                
        
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)


        bsInternal._tournamentQuery(args={'tournamentIDs':[tournamentID],
                                          'numScores':50,
                                          'source':'scores window'},
                                    callback=bs.WeakCall(self._onTournamentQueryResponse))
        # bsUtils.serverGet('bsTournamentQuery',{'buildNumber':bs.getEnvironment()['buildNumber'],
        #                                        'tournamentIDs':repr([tournamentID]),
        #                                        'numScores':50},
        #                   callback=bs.WeakCall(self._onTournamentQueryResponse))


    def _onTournamentQueryResponse(self,data):
        if data is not None:
            data = data['t'] # this used to be the whole payload
            # kill our loading text if we've got scores.. otherwise just replace it with 'no scores yet'
            if len(data[0]['scores']) > 0:
                self._loadingText.delete()
            else: bs.textWidget(edit=self._loadingText,text=bs.getResource('noScoresYetText'))
            incr = 30
            #print 'WOULD SHOW DATA',len(data[0]['scores'])
            subWidth = self._width-90
            subHeight = 30+len(data[0]['scores'])*incr
            self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(subWidth,subHeight),background=False)
            for i,entry in enumerate(data[0]['scores']):
                
                bs.textWidget(parent=self._subContainer,
                              position=(subWidth*0.1-5,subHeight-20-incr*i),
                              maxWidth=20,
                              scale=0.5,
                              color=(0.6,0.6,0.7),flatness=1.0,shadow=0.0,
                              text=str(i+1),
                              size=(0,0),
                              hAlign='right',vAlign='center')
                
                bs.textWidget(parent=self._subContainer,
                              position=(subWidth*0.25-2,subHeight-20-incr*i),
                              maxWidth=subWidth*0.24,
                              color=(0.9,1.0,0.9),flatness=1.0,shadow=0.0,
                              scale=0.6,
                              text=(bsUtils.getTimeString(entry[0]*10,centi=True) if data[0]['scoreType'] == 'time' else str(entry[0])),
                              size=(0,0),
                              hAlign='center',vAlign='center')

                t = bs.textWidget(parent=self._subContainer,
                                  position=(subWidth*0.25,subHeight-20-incr*i - (0.5/0.7)*incr),
                                  maxWidth=subWidth*0.6,
                                  scale=0.7,flatness=1.0,shadow=0.0,
                                  text=entry[1],
                                  selectable=True,
                                  clickActivate=True,
                                  autoSelect=True,
                                  extraTouchBorderScale=0.0,
                                  size=((subWidth*0.6)/0.7,incr/0.7),
                                  hAlign='left',vAlign='center')
                
                bs.textWidget(edit=t,onActivateCall=bs.Call(self._showPlayerInfo,entry,t))
                if i == 0:
                    bs.widget(edit=t,upWidget=self._cancelButton)
                    
            # dont wanna cache this - its got scores and stuff we dont need to keep
            #_cacheTournamentInfo(data)
            #self._secondsRemaining = gTournamentInfo[self._tournamentID]['timeRemaining']
    def _showPlayerInfo(self,entry,textWidget):
        # for the moment we only work if a single player-info is present..
        if len(entry[2]) != 1:
            bs.playSound(bs.getSound('error'))
            return
        bs.playSound(bs.getSound('swish'))
        AccountInfoWindow(accountID=entry[2][0].get('a',None),
                          profileID=entry[2][0].get('p',None),
                          position=textWidget.getScreenSpaceCenter())
        self._transitionOut()
        
    def _onCancelPress(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            #self._saveState()
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            if self._onCloseCall is not None:
                self._onCloseCall()

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()


class AccountInfoWindow(PopupWindow):

    def __init__(self,accountID,profileID=None,position=(0,0),scale=None,offset=(0,0)):

        self._accountID = accountID
        self._profileID = profileID
        
        if scale is None: scale = 2.6 if gSmallUI else 1.8 if gMedUI else 1.4
        self._transitioningOut = False
        
        self._width = 400
        self._height = 300 if gSmallUI else 400 if gMedUI else 450

        bgColor = (0.5,0.4,0.6)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor,offset=offset)

        env = bs.getEnvironment()

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-20),size=(0,0),hAlign='center',vAlign='center',
                                        scale=0.6,text=bs.getResource('playerInfoText'),maxWidth=200,color=(0.7,0.7,0.7,0.7))

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._width-60,self._height-70),position=(30,30),captureArrows=True,simpleCullingV=10)
        bs.widget(edit=self._scrollWidget,autoSelect=True)

        self._loadingText = bs.textWidget(parent=self._scrollWidget,
                                          scale=0.5,
                                          text=bs.getResource('loadingText')+'...',
                                          size=(self._width-60,100),
                                          hAlign='center',vAlign='center')

        # in cases where the user most likely has a browser/email, lets
        # offer a 'report this user' button..
        if bsUtils.isBrowserLikelyAvailable():

            self._extrasMenuButton = b = bs.buttonWidget(parent=self._rootWidget, size=(20, 20), position=(self._width - 60, self._height - 30),
                                                     autoSelect=True, label='...', buttonType='square', color=(0.64, 0.52, 0.69),
                                                     textColor=(0.57, 0.47, 0.57), onActivateCall=self._onExtrasMenuPress)
            
            # self._moreButton = b = bs.buttonWidget(parent=self._rootWidget,
            #                                        size=(100,22),
            #                                        position=(self._width*0.5-58,7),
            #                                        color=(0.54,0.42,0.56),
            #                                        autoSelect=True,
            #                                        textColor=(0.67,0.57,0.67),
            #                                        onActivateCall=self._onMorePress,
            #                                        textScale=0.6,
            #                                        label=bs.getResource('coopSelectWindow.seeMoreText'),
            #                                        textFlatness=1.0)
            # bs.widget(edit=self._scrollWidget,rightWidget=b)
            # self._reportThisPlayerButton = b = bs.buttonWidget(parent=self._rootWidget,
            #                                                    size=(100,18),
            #                                                    position=(self._width*0.8-58,9),
            #                                                    color=(0.54,0.42,0.56),
            #                                                    autoSelect=True,
            #                                                    textScale=0.6,
            #                                                    textColor=(0.57,0.47,0.57),
            #                                                    onActivateCall=self._onReportPress,
            #                                                    label=bs.getResource('reportThisPlayerText'),
            #                                                    textFlatness=1.0)
            # bs.widget(edit=self._scrollWidget,rightWidget=b)
        
        
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)

        bsUtils.serverGet('bsAccountInfo',{'buildNumber':bs.getEnvironment()['buildNumber'],
                                           'accountID':repr(self._accountID),
                                           'profileID':repr(self._profileID)},
                          callback=bs.WeakCall(self._onQueryResponse))

    def popupMenuSelectedChoice(self, window, choice):
        if choice == 'more':
            self._onMorePress()
        elif choice == 'report':
            self._onReportPress()
        else:
            print 'ERROR: unknown account info extras menu item:',choice

    def popupMenuClosing(self, window):
        pass
    
    def _onExtrasMenuPress(self):
        PopupMenuWindow(position=self._extrasMenuButton.getScreenSpaceCenter(),
                        scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23,
                        choices=['more','report'],
                        choicesDisplay=[bs.getResource('coopSelectWindow.seeMoreText'),
                                        bs.getResource('reportThisPlayerText')],
                        currentChoice='more',
                        delegate=self).getRootWidget()
        
    def _onReportPress(self):
        import bsUI2
        bsUI2.ReportPlayerWindow(self._accountID,originWidget=self._extrasMenuButton)

    def _onMorePress(self):
        bs.openURL(bsInternal._getServerAddress()+'/highscores?profile='+self._accountID)
        
    def _onQueryResponse(self,data):
        # data = None
        if data is None:
            bs.textWidget(edit=self._loadingText,text=bs.getResource('internal.unavailableNoConnectionText'))
        else:
            try:
                # at some point should actually get this as json; prepping for that..
                data = bsUtils.jsonPrep(data)
                
                import bsAchievement
                import bsSpaz
                self._loadingText.delete()
                # print 'GOT DATA',data
                # bs.textWidget(edit=self._loadingText,text='got valid response')
                ts = ''
                try:
                    #ts = '\xee\x80\xaf' * random.randrange(200)
                    ts = data['trophies']
                    #uni = ts.decode('utf-8')
                    n = 10
                    chunks = [ts[i:i + n] for i in range(0, len(ts), n)]
                    ts = ('\n\n'.join(chunks))
                    if ts == '': ts = '-'
                except Exception:
                    bs.printException("Error displaying trophies")
                accountNameSpacing = 15
                tscale = 0.65
                tsHeight = bs.getStringHeight(ts)
                subWidth = self._width-80
                subHeight = 200 + tsHeight * tscale + accountNameSpacing * len(data['accountDisplayStrings'])
                self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(subWidth,subHeight),background=False)
                v = subHeight - 20

                titleScale = 0.37
                center = 0.5
                maxWidthScale = 0.9
                center = 0.3
                maxWidthScale = 0.45
                showingCharacter = False
                if data['profileDisplayString'] is not None:
                    tintColor = (1,1,1)
                    try:
                        if data['profile'] is not None:
                            profile = data['profile']
                            character = bsSpaz.appearances.get(profile['character'],None)
                            if character is not None:
                                tintColor=profile['color'] if 'color' in profile else (1,1,1)
                                tint2Color=profile['highlight'] if 'highlight' in profile else (1,1,1)
                                iconTex = character.iconTexture
                                tintTex = character.iconMaskTexture
                                maskTexture=bs.getTexture('characterIconMask')
                                bs.imageWidget(parent=self._subContainer,position=(subWidth*center-40,v-80),
                                               size=(80,80),
                                               color=(1,1,1),
                                               maskTexture=maskTexture,
                                               texture=bs.getTexture(iconTex),
                                               tintTexture=bs.getTexture(tintTex),
                                               tintColor=tintColor,tint2Color=tint2Color)
                                v -= 95
                    except Exception:
                        bs.printException("Error displaying character")
                    bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),
                                  hAlign='center',vAlign='center',scale=0.9,color=bs.getSafeColor(tintColor,0.7),
                                  shadow=1.0, text=data['profileDisplayString'],maxWidth=subWidth*maxWidthScale*0.75)
                    showingCharacter = True
                    v -= 33

                center = 0.75 if showingCharacter else 0.5
                maxWidthScale = 0.45 if showingCharacter else 0.9
                
                v = subHeight - 20
                if len(data['accountDisplayStrings']) <= 1: accountTitle = bs.getResource('settingsWindow.accountText')
                else: accountTitle = bs.getResource('accountSettingsWindow.accountsText',fallback='settingsWindow.accountText')
                bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),flatness=1.0,
                              hAlign='center',vAlign='center',scale=titleScale,color=gInfoTextColor,
                              text=accountTitle,
                              maxWidth=subWidth*maxWidthScale)
                drawSmall = True if (showingCharacter or len(data['accountDisplayStrings']) > 1) else False
                v -= 14 if drawSmall else 20
                for accountString in data['accountDisplayStrings']:
                    bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),
                                  hAlign='center',vAlign='center',scale=0.55 if drawSmall else 0.8,
                                  text=accountString,maxWidth=subWidth*maxWidthScale)
                    v -= accountNameSpacing

                v += accountNameSpacing
                v -= 25 if showingCharacter else 29
                
                bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),flatness=1.0,
                              hAlign='center',vAlign='center',scale=titleScale,color=gInfoTextColor,
                              text=bs.getResource('rankText'),maxWidth=subWidth*maxWidthScale)
                v -= 14
                if data['rank'] is None:
                    rankStr = '-'
                    suffixOffset = None
                else:
                    strRaw = bs.getResource('league.rankInLeagueText')
                    rankStr = (strRaw.replace('${RANK}',str(data['rank'][2]))
                               .replace('${NAME}',bs.translate('leagueNames',data['rank'][0]))
                               .replace('${SUFFIX}',''))
                    rankStrWidth = min(subWidth*maxWidthScale, bs.getStringWidth(rankStr) * 0.55)
                    # only tack our suffix on if its at the end and only for non-diamond leagues
                    if strRaw.endswith('${SUFFIX}') and data['rank'][0] != 'Diamond':
                        suffixOffset = rankStrWidth*0.5+2
                    else: suffixOffset = None
                    
                    
                bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),
                              hAlign='center',vAlign='center',scale=0.55,
                              text=rankStr,
                              maxWidth=subWidth*maxWidthScale)
                if suffixOffset is not None:
                    bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center+suffixOffset,v+3),
                                  hAlign='left',vAlign='center',scale=0.29,flatness=1.0,
                                  text='['+str(data['rank'][1])+']')
                v -= 14

                strRaw = bs.getResource('league.rankInLeagueText')
                oldOffs = -50
                prevRanksShown = 0
                for prevRank in data['prevRanks']:
                    rankStr = bs.getResource('league.seasonText').replace('${NUMBER}',str(prevRank[0]))+':    '
                    rankStr += (strRaw.replace('${RANK}',str(prevRank[3]))
                               .replace('${NAME}',bs.translate('leagueNames',prevRank[1]))
                               .replace('${SUFFIX}',''))
                    rankStrWidth = min(subWidth*maxWidthScale, bs.getStringWidth(rankStr) * 0.3)
                    # only tack our suffix on if its at the end and only for non-diamond leagues
                    if strRaw.endswith('${SUFFIX}') and prevRank[1] != 'Diamond':
                        suffixOffset = rankStrWidth+2
                    else: suffixOffset = None
                    bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center+oldOffs,v),
                                  hAlign='left',vAlign='center',scale=0.3,
                                  text=rankStr,flatness=1.0,
                                  maxWidth=subWidth*maxWidthScale)
                    if suffixOffset is not None:
                        bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center+oldOffs+suffixOffset,v+1),
                                      hAlign='left',vAlign='center',scale=0.20,flatness=1.0,
                                      text='['+str(prevRank[2])+']')
                    prevRanksShown += 1
                    v -= 10

                v -= 13
                
                bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),flatness=1.0,
                              hAlign='center',vAlign='center',scale=titleScale,color=gInfoTextColor,
                              text=bs.getResource('achievementsText'),maxWidth=subWidth*maxWidthScale)
                v -= 14
                bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),
                              hAlign='center',vAlign='center',scale=0.55,
                              text=str(data['achievementsCompleted'])+' / '+str(len(bsAchievement.gAchievements)),maxWidth=subWidth*maxWidthScale)
                v -= 25

                if prevRanksShown == 0 and showingCharacter: v -= 20
                elif prevRanksShown == 1 and showingCharacter: v -= 10
                
                #v -= 10 if showingCharacter else 0

                center = 0.5
                maxWidthScale = 0.9
                
                bs.textWidget(parent=self._subContainer,size=(0,0),position=(subWidth*center,v),
                              hAlign='center',vAlign='center',scale=titleScale,color=gInfoTextColor,flatness=1.0,
                              text=bs.getResource('trophiesThisSeasonText',fallback='trophiesText'),maxWidth=subWidth*maxWidthScale)
                v -= 19
                bs.textWidget(parent=self._subContainer,size=(0,tsHeight),position=(subWidth*0.5,v-tsHeight*tscale),
                              hAlign='center',vAlign='top',cornerScale=tscale,
                              text=ts)
                
                
            except Exception:
                bs.printException('Error displaying account info')
    
    def _onCancelPress(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            # if self._onCloseCall is not None:
            #     self._onCloseCall()

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()

        
class CharacterPicker(PopupWindow):

    def __init__(self,parent,position=(0,0),delegate=None,scale=None,offset=(0,0),
                 tintColor=(1,1,1),tint2Color=(1,1,1),selectedCharacter=None):
        if scale is None: scale = 1.85 if gSmallUI else 1.65 if gMedUI else 1.23

        self._delegate = delegate
        self._transitioningOut = False

        # make a list of spaz icons
        self._spazzes = bsSpaz.getAppearances()
        self._spazzes.sort()
        self._iconTextures = [bs.getTexture(bsSpaz.appearances[s].iconTexture) for s in self._spazzes]
        self._iconTintTextures = [bs.getTexture(bsSpaz.appearances[s].iconMaskTexture) for s in self._spazzes]
        
        count = len(self._spazzes)
        
        columns = 3
        rows = int(math.ceil(float(count)/columns))
        
        buttonWidth = 100
        buttonHeight = 100
        buttonBufferH = 10
        buttonBufferV = 15
        
        self._width = 10+columns*(buttonWidth+2*buttonBufferH)*(1.0/0.95)*(1.0/0.8)
        self._height = self._width*(0.8 if gSmallUI else 1.06)

        self._scrollWidth = self._width * 0.8
        self._scrollHeight = self._height * 0.8
        self._scrollPosition = ((self._width-self._scrollWidth)*0.5,(self._height-self._scrollHeight)*0.5)
        #self._scrollPosition = ((self._width-self._scrollWidth)*-0.2,(self._height-self._scrollHeight)*1.3)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),scale=scale,
                             bgColor=(0.5,0.5,0.5),offset=offset,
                             focusPosition=self._scrollPosition,
                             focusSize=(self._scrollWidth,self._scrollHeight))

        
        
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._scrollWidth,self._scrollHeight),
                                             color=(0.55,0.55,0.55),highlight=False,
                                             position=self._scrollPosition)
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)

        self._subWidth = self._scrollWidth*0.95
        self._subHeight = 5+rows*(buttonHeight+2*buttonBufferV) + 100
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),
                                                background=False)

        # bs.buttonWidget(edit=self._characterButton,
        #                texture=self._iconTextures[self._iconIndex],
        #                tintTexture=self._iconTintTextures[self._iconIndex],
        #                tintColor=self._color,
        #                tint2Color=self._highlight)
        # bs.textWidget(edit=self._charNameWidget,text="- "+bs.translate('characterNames',self._spazzes[self._iconIndex])+" -")

        index = 0
        maskTexture=bs.getTexture('characterIconMask')
        for y in range(rows):
            for x in range(columns):
                pos = (x*(buttonWidth+2*buttonBufferH)+buttonBufferH,
                       self._subHeight - (y+1)*(buttonHeight+2*buttonBufferV)+12)
                b = bs.buttonWidget(parent=self._subContainer,buttonType='square',size=(buttonWidth,buttonHeight),
                                    autoSelect=True,
                                    texture=self._iconTextures[index],
                                    tintTexture=self._iconTintTextures[index],
                                    maskTexture=maskTexture,
                                    label='',
                                    color=(1,1,1),
                                    tintColor=tintColor,
                                    tint2Color=tint2Color,
                                    onActivateCall=bs.Call(self._selectCharacter,self._spazzes[index]),
                                    position=pos)
                bs.widget(edit=b,showBufferTop=60,showBufferBottom=60)
                if self._spazzes[index] == selectedCharacter:
                    bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)
                name = bs.translate('characterNames',self._spazzes[index])
                bs.textWidget(parent=self._subContainer,text=name,position=(pos[0]+buttonWidth*0.5,pos[1]-12),
                              size=(0,0),scale=0.5,maxWidth=buttonWidth,
                              drawController=b,hAlign='center',vAlign='center',color=(0.8,0.8,0.8,0.8))
                index += 1
                
                if index >= count: break
            if index >= count: break
        self._getMoreCharactersButton = b = bs.buttonWidget(parent=self._subContainer,
                                                            size=(self._subWidth*0.8,60),position=(self._subWidth*0.1,30),
                                                            label=bs.getResource('editProfileWindow.getMoreCharactersText'),
                                                            onActivateCall=self._onStorePress,
                                                            color=(0.6,0.6,0.6),
                                                            textColor=(0.8,0.8,0.8),
                                                            autoSelect=True)
        bs.widget(edit=b,showBufferTop=30,showBufferBottom=30)

    def _onStorePress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._transitionOut()
        StoreWindow(modal=True,showTab='characters',originWidget=self._getMoreCharactersButton)
        
    def _selectCharacter(self,character):
        if self._delegate is not None: self._delegate.onCharacterPickerPick(character)
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()

class IconPicker(PopupWindow):

    def __init__(self,parent,position=(0,0),delegate=None,scale=None,offset=(0,0),
                 tintColor=(1,1,1),tint2Color=(1,1,1),selectedIcon=None):
        if scale is None: scale = 1.85 if gSmallUI else 1.65 if gMedUI else 1.23

        self._delegate = delegate
        self._transitioningOut = False

        # make a list of spaz icons
        #self._spazzes = bsSpaz.getAppearances()
        #self._spazzes.sort()
        self._icons = [bs.getSpecialChar('logo')] + _getPurchasedIcons()
        
        # self._iconTextures = [bs.getTexture(bsSpaz.appearances[s].iconTexture) for s in self._spazzes]
        # self._iconTintTextures = [bs.getTexture(bsSpaz.appearances[s].iconMaskTexture) for s in self._spazzes]
        
        count = len(self._icons)
        
        columns = 4
        rows = int(math.ceil(float(count)/columns))
        
        buttonWidth = 50
        buttonHeight = 50
        buttonBufferH = 10
        buttonBufferV = 5
        
        self._width = 10+columns*(buttonWidth+2*buttonBufferH)*(1.0/0.95)*(1.0/0.8)
        self._height = self._width*(0.8 if gSmallUI else 1.06)

        self._scrollWidth = self._width * 0.8
        self._scrollHeight = self._height * 0.8
        self._scrollPosition = ((self._width-self._scrollWidth)*0.5,(self._height-self._scrollHeight)*0.5)
        #self._scrollPosition = ((self._width-self._scrollWidth)*-0.2,(self._height-self._scrollHeight)*1.3)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),scale=scale,
                             bgColor=(0.5,0.5,0.5),offset=offset,
                             focusPosition=self._scrollPosition,
                             focusSize=(self._scrollWidth,self._scrollHeight))

        
        
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._scrollWidth,self._scrollHeight),
                                             color=(0.55,0.55,0.55),highlight=False,
                                             position=self._scrollPosition)
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)

        self._subWidth = self._scrollWidth*0.95
        self._subHeight = 5+rows*(buttonHeight+2*buttonBufferV) + 100
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),
                                                background=False)

        # bs.buttonWidget(edit=self._characterButton,
        #                texture=self._iconTextures[self._iconIndex],
        #                tintTexture=self._iconTintTextures[self._iconIndex],
        #                tintColor=self._color,
        #                tint2Color=self._highlight)
        # bs.textWidget(edit=self._charNameWidget,text="- "+bs.translate('characterNames',self._spazzes[self._iconIndex])+" -")

        index = 0
        #maskTexture=bs.getTexture('characterIconMask')
        for y in range(rows):
            for x in range(columns):
                pos = (x*(buttonWidth+2*buttonBufferH)+buttonBufferH,
                       self._subHeight - (y+1)*(buttonHeight+2*buttonBufferV)+0)
                b = bs.buttonWidget(parent=self._subContainer,buttonType='square',size=(buttonWidth,buttonHeight),
                                    autoSelect=True,
                                    textScale=1.2,
                                    #label=self._icons[index],
                                    label='',
                                    color=(0.65,0.65,0.65),
                                    onActivateCall=bs.Call(self._selectIcon,self._icons[index]),
                                    position=pos)
                bs.textWidget(parent=self._subContainer,hAlign='center',vAlign='center',
                              size=(0,0),position=(pos[0]+0.5*buttonWidth-1,pos[1]+15),
                              drawController=b,text=self._icons[index],scale=1.8)
                bs.widget(edit=b,showBufferTop=60,showBufferBottom=60)
                if self._icons[index] == selectedIcon:
                    bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)
                #name = bs.translate('characterNames',self._spazzes[index])
                # bs.textWidget(parent=self._subContainer,text=name,position=(pos[0]+buttonWidth*0.5,pos[1]-12),
                #               size=(0,0),scale=0.5,maxWidth=buttonWidth,
                #               drawController=b,hAlign='center',vAlign='center',color=(0.8,0.8,0.8,0.8))
                index += 1
                
                if index >= count: break
            if index >= count: break
        self._getMoreIconsButton = b = bs.buttonWidget(parent=self._subContainer,
                                                       size=(self._subWidth*0.8,60),position=(self._subWidth*0.1,30),
                                                       label=bs.getResource('editProfileWindow.getMoreIconsText'),
                                                       onActivateCall=self._onStorePress,
                                                       color=(0.6,0.6,0.6),
                                                       textColor=(0.8,0.8,0.8),
                                                       autoSelect=True)
        bs.widget(edit=b,showBufferTop=30,showBufferBottom=30)

    def _onStorePress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._transitionOut()
        StoreWindow(modal=True,showTab='icons',originWidget=self._getMoreIconsButton)
        
    def _selectIcon(self,icon):
        if self._delegate is not None: self._delegate.onIconPickerPick(icon)
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()
        
class UpgradeProfileWindow(Window):

        
    def __init__(self,editProfileWindow,transition='inRight'):

        self._R = bs.getResource('editProfileWindow')

        self._width = 680
        #self._height = 350 if gSmallUI else 400 if gMedUI else 450
        self._height = 350
        self._baseScale = 2.05 if gSmallUI else 1.5 if gMedUI else 1.2
        self._upgradeStartTime = None
        self._name = editProfileWindow.getName()

        self._editProfileWindow = weakref.ref(editProfileWindow)
        
        topExtra = 15 if gSmallUI else 15
        self._rootWidget = bs.containerWidget(size=(self._width, self._height+topExtra),
                                              transition=transition,
                                              scale=self._baseScale,
                                              stackOffset=(0,15) if gSmallUI else (0,0))
        cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(52,30),size=(155,60),scale=0.8,
                            autoSelect=True,label=bs.getResource('cancelText'),onActivateCall=self._cancel)
        self._upgradeButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width - 190,30),size=(155,60),scale=0.8,
                                            autoSelect=True,label=bs.getResource('upgradeText'),onActivateCall=self._onUpgradePress)
        bs.containerWidget(edit=self._rootWidget,cancelButton=cancelButton,startButton=self._upgradeButton,
                           selectedChild=self._upgradeButton)

        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-38),size=(0,0),
                          text=(self._R.upgradeToGlobalProfileText),
                          color=gTitleColor,maxWidth=self._width * 0.45,
                          scale=1.0,hAlign="center",vAlign="center")

        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-100),size=(0,0),
                          text=self._R.upgradeProfileInfoText,
                          color=gInfoTextColor,maxWidth=self._width * 0.8,
                          scale=0.7,hAlign="center",vAlign="center")

        self._statusText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-160),size=(0,0),
                                         text=self._R.checkingAvailabilityText.replace('${NAME}',self._name),
                                         color=(0.8, 0.4, 0.0), maxWidth=self._width * 0.8,
                                         scale=0.65,hAlign="center",vAlign="center")

        self._priceText  = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-230),size=(0,0),
                                         text='',
                                         color=(1.0, 0.5, 0.0), maxWidth=self._width * 0.8,
                                         scale=1.5,hAlign="center",vAlign="center")

        self._ticketsText = bs.textWidget(parent=self._rootWidget,
                                          position=(self._width*0.9-5,self._height-30),size=(0,0),
                                          text=bs.getSpecialChar('ticket')+'123',
                                          color=(1.0, 0.5, 0.0), maxWidth=100,
                                          scale=0.5,hAlign="right",vAlign="center")

        bsUtils.serverGet('bsGlobalProfileCheck',{'name':self._name},
                          callback=bs.WeakCall(self._profileCheckResult))
        self._cost = bsInternal._getAccountMiscReadVal('price.global_profile',500)
        self._status = 'waiting'
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._update()

    def _profileCheckResult(self,result):
        if result is None:
            bs.textWidget(edit=self._statusText,text=bs.getResource('internal.unavailableNoConnectionText'),color=(1,0,0))
            self._status = 'error'
            bs.buttonWidget(edit=self._upgradeButton,color=(0.4,0.4,0.4),textColor=(0.5,0.5,0.5))
        else:
            if result['available']:
                bs.textWidget(edit=self._statusText,text=self._R.availableText.replace('${NAME}',self._name),color=(0,1,0))
                bs.textWidget(edit=self._priceText, text=bs.getSpecialChar('ticket')+str(self._cost))
                self._status = None
            else:
                bs.textWidget(edit=self._statusText,text=self._R.unavailableText.replace('${NAME}',self._name),color=(1,0,0))
                self._status = 'unavailable'
                bs.buttonWidget(edit=self._upgradeButton,color=(0.4,0.4,0.4),textColor=(0.5,0.5,0.5))
                
    def _onUpgradePress(self):
        if self._status is None:
            # if it appears we don't have enough tickets, offer to buy more
            tickets = bsInternal._getAccountTicketCount()
            if tickets < self._cost:
                bs.playSound(bs.getSound('error'))
                showGetTicketsPrompt()
                return
            bs.screenMessage(bs.getResource('purchasingText'),color=(0,1,0))
            self._status = 'pre_upgrading'
            # bs.containerWidget(edit=self._rootWidget,transition='outLeft')

            # now we tell the original editor to save the profile, add an upgrade transaction,
            # and then sit and wait for everything to go through..
            editProfileWindow = self._editProfileWindow()
            if editProfileWindow is None:
                print 'profile upgrade: original edit window gone'
                return
            success = editProfileWindow.save(transitionOut=False)
            if not success:
                print 'profile upgrade: error occurred saving profile'
                bs.screenMessage(bs.getResource('errorText'),color=(1,0,0))
                bs.playSound(bs.getSound('error'))
                return
            bsInternal._addTransaction({'type':'UPGRADE_PROFILE',
                                        'name':self._name})
            bsInternal._runTransactions()
            self._status = 'upgrading'
            self._upgradeStartTime = time.time()
        else:
            bs.playSound(bs.getSound('error'))
        
    def _update(self):
        try: tStr = str(bsInternal._getAccountTicketCount())
        except Exception: tStr = '?'
        bs.textWidget(edit=self._ticketsText,text=bs.getResource('getTicketsWindow.youHaveShortText').replace('${COUNT}',bs.getSpecialChar('ticket')+tStr))

        # once we've kicked off an upgrade attempt and all transactions go through, we're done
        if (self._status == 'upgrading' and not bsInternal._haveOutstandingTransactions()):
            self._status = 'exiting'
            bs.containerWidget(edit=self._rootWidget,transition='outRight')
            editProfileWindow = self._editProfileWindow()
            if editProfileWindow is None:
                print 'profile upgrade transition out: original edit window gone'
                return
            bs.playSound(bs.getSound('gunCocking'))
            editProfileWindow.reloadWindow()
            
        
        
    def _cancel(self):
        # if we recently sent out an upgrade request, disallow canceling for a bit.
        if self._upgradeStartTime is not None and time.time() - self._upgradeStartTime < 10.0:
            bs.playSound(bs.getSound('error'))
            return
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        
class EditProfileWindow(Window):

    def reloadWindow(self):
        # kinda hacky for now - we just transition out and recreate ourself..
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = EditProfileWindow(self.getName(),self._inMainMenu).getRootWidget()
        
    def __init__(self,existingProfile,inMainMenu,transition='inRight'):

        import bsMainMenu
        
        self._inMainMenu=inMainMenu
        self._existingProfile = existingProfile
        self._colorPickers = {}

        self._R = R = bs.getResource('editProfileWindow')

        # grab profile colors or pick random ones
        self._color,self._highlight = bsUtils.getPlayerProfileColors(existingProfile)
        self._width = width = 680
        self._height = height = 350 if gSmallUI else 400 if gMedUI else 450
        spacing = 40
        buttonWidth = 350
        self._baseScale = 2.05 if gSmallUI else 1.5 if gMedUI else 1.0

        topExtra = 15 if gSmallUI else 15
        self._rootWidget = bs.containerWidget(size=(width,height+topExtra),transition=transition,
                                              scale=self._baseScale,
                                              stackOffset=(0,15) if gSmallUI else (0,0))
        cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(52,height-60),size=(155,60),scale=0.8,
                            autoSelect=True,label=bs.getResource('cancelText'),onActivateCall=self._cancel)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        saveButton = b = bs.buttonWidget(parent=self._rootWidget,position=(width-177,height-60),size=(155,60),autoSelect=True,
                                         scale=0.8,label=bs.getResource('saveText'))
        bs.widget(edit=saveButton,leftWidget=cancelButton)
        bs.widget(edit=cancelButton,rightWidget=saveButton)
        bs.containerWidget(edit=self._rootWidget,startButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,height-38),size=(0,0),
                          text=(R.titleNewText if existingProfile is None else R.titleEditText),
                          color=gTitleColor,maxWidth=290,
                          scale=1.0,hAlign="center",vAlign="center")

        # make a list of spaz icons
        self.refreshCharacters()
        try: profile = bs.getConfig()['Player Profiles'][self._existingProfile]
        except Exception: profile = {}

        if 'global' in profile:
            self._global = profile['global']
        else:
            self._global = False

        if 'icon' in profile:
            self._icon = profile['icon']
            # if type(self._icon) is unicode:
            #     self._icon = self._icon.encode('utf-8') # we expect a utf8 string for now..
        else:
            self._icon = bs.getSpecialChar('logo')
        
        assignedRandomChar = False
        
        # look for existing character choice or pick random one otherwise
        try: iconIndex = self._spazzes.index(profile['character'])
        except Exception:
            # lets set the default icon to spaz for our first profile; after that we go random
            # (SCRATCH THAT.. we now hard-code account-profiles to start with spaz which has a similar effect)
            # try: pLen = len(bs.getConfig()['Player Profiles'])
            # except Exception: pLen = 0
            # if pLen == 0: iconIndex = self._spazzes.index('Spaz')
            # else:
            random.seed()
            iconIndex = random.randrange(len(self._spazzes))
            assignedRandomChar = True
        self._iconIndex = iconIndex
        bs.buttonWidget(edit=saveButton,onActivateCall=lambda: self.save())

        v = height - 115

        self._name = u'' if self._existingProfile is None else self._existingProfile

        self._isAccountProfile = (self._name == '__account__')

        # if we just picked a random character, see if it has specific colors/highlights associated with it
        # and assign them if so..
        if assignedRandomChar:
            c = bsSpaz.appearances[self._spazzes[iconIndex]].defaultColor
            if c is not None: self._color = c
            h = bsSpaz.appearances[self._spazzes[iconIndex]].defaultHighlight
            if h is not None: self._highlight = h
        
        # assign a random name if they had none..
        if self._name == u'':
            names = bsInternal._getRandomNames()
            self._name = names[random.randrange(len(names))]

        if not self._isAccountProfile and not self._global:
            bs.textWidget(parent=self._rootWidget,text=R.nameText,position=(200,v-6),size=(0,0),hAlign='right',vAlign='center',color=(1,1,1,0.5),scale=0.9)

        self._upgradeButton = None
        if self._isAccountProfile:
            if bsInternal._getAccountState() == 'SIGNED_IN': s = bsInternal._getAccountDisplayString()
            else: s = u'??'
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,v-7),size=(0,0),scale=1.2,
                          text=s,maxWidth=270,hAlign='center',vAlign='center')
            txt = bs.getResource('editProfileWindow.accountProfileText')
            bWidth = min(270, bs.getStringWidth(txt) * 0.6)
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,v-39),size=(0,0),scale=0.6,color=gInfoTextColor,
                          text=txt,maxWidth=270,hAlign='center',vAlign='center')
            self._accountTypeInfoButton = bs.buttonWidget(parent=self._rootWidget,label='?',size=(15, 15),textScale=0.6,
                                                    position=(self._width*0.5+bWidth*0.5+13,v-47),buttonType='square',
                                                    color=(0.6, 0.5, 0.65), autoSelect=True,
                                                    onActivateCall=self.showAccountProfileInfo)
        elif self._global:

            bSize = 60
            self._iconButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(self._width*0.5-160-bSize*0.5,v-38-15),
                                                   size=(bSize,bSize),color=(0.6,0.5,0.6),label='',buttonType='square',
                                                   textScale=1.2, onActivateCall=self._onIconPress)
            self._iconButtonLabel = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5-160,v-35),drawController=b,
                                                   hAlign='center',vAlign='center',size=(0,0),color=(1,1,1),text='',scale=2.0)

            bs.textWidget(parent=self._rootWidget,hAlign='center',vAlign='center',position=(self._width*0.5-160,v-55-15),size=(0,0),
                          drawController=b,text=R.iconText,scale=0.7,color=gTitleColor,maxWidth=120)

            self._updateIcon()
            
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,v-7),size=(0,0),scale=1.2,
                          text=self._name,maxWidth=240,hAlign='center',vAlign='center')
            txt = bs.getResource('editProfileWindow.globalProfileText')
            bWidth = min(240, bs.getStringWidth(txt)*0.6)
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,v-39),size=(0,0),scale=0.6,color=gInfoTextColor,
                          text=txt,maxWidth=240,hAlign='center',vAlign='center')
            self._accountTypeInfoButton = bs.buttonWidget(parent=self._rootWidget,label='?',size=(15, 15),textScale=0.6,
                                                          position=(self._width*0.5+bWidth*0.5+13,v-47),buttonType='square',
                                                          color=(0.6, 0.5, 0.65), autoSelect=True,
                                                          onActivateCall=self.showGlobalProfileInfo)
        else:
            self._textField = bs.textWidget(parent=self._rootWidget,position=(220,v-30),size=(265,40),
                                            text=self._name,hAlign='left',
                                            vAlign='center',maxChars=16,
                                            description=R.nameDescriptionText,
                                            autoSelect=True,
                                            editable=True,padding=4,
                                            color=(0.9,0.9,0.9,1.0),
                                            onReturnPressCall=bs.Call(saveButton.activate))
            txt = bs.getResource('editProfileWindow.localProfileText')
            bWidth = min(270, bs.getStringWidth(txt) * 0.6)
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,v-43),
                          size=(0,0),scale=0.6,color=gInfoTextColor,
                          text=txt,maxWidth=270,hAlign='center',vAlign='center')
            self._accountTypeInfoButton = bs.buttonWidget(parent=self._rootWidget,label='?',size=(15, 15),textScale=0.6,
                                                    position=(self._width*0.5+bWidth*0.5+13,v-50),buttonType='square',
                                                    color=(0.6, 0.5, 0.65), autoSelect=True,
                                                    onActivateCall=self.showLocalProfileInfo)
            self._upgradeButton = bs.buttonWidget(parent=self._rootWidget,label=bs.getResource('upgradeText'),size=(40, 17),
                                                  textScale=1.0,buttonType='square',
                                                  position=(self._width*0.5+bWidth*0.5+13+43,v-51),
                                                  color=(0.6, 0.5, 0.65), autoSelect=True,
                                                  onActivateCall=self.upgradeProfile)

        v -= spacing * 3.0

        h = 256
        bSize = 80
        bSize2 = 100
        bOffs = 150

        imgSize = 100
        self._colorButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(self._width*0.5-bOffs-bSize*0.5,v-50),
                                                size=(bSize,bSize),color=self._color,label='',buttonType='square')
        origin = self._colorButton.getScreenSpaceCenter()
        bs.buttonWidget(edit=self._colorButton,onActivateCall=bs.WeakCall(self._makePicker,'color',origin))
        bs.textWidget(parent=self._rootWidget,hAlign='center',vAlign='center',position=(self._width*0.5-bOffs,v-65),size=(0,0),
                      drawController=b,text=R.colorText,scale=0.7,color=gTitleColor,maxWidth=120)

        self._characterButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(self._width*0.5-bSize2*0.5,v-60),
                                                    upWidget=self._accountTypeInfoButton,onActivateCall=self._onCharacterPress,size=(bSize2,bSize2),label='',color=(1,1,1),maskTexture=bs.getTexture('characterIconMask'))
        if not self._isAccountProfile and not self._global:
            bs.containerWidget(edit=self._rootWidget,selectedChild=self._textField)
        bs.textWidget(parent=self._rootWidget,hAlign='center',vAlign='center',position=(self._width*0.5,v-80),size=(0,0),
                      drawController=b,text=R.characterText,scale=0.7,color=gTitleColor,maxWidth=130)
        
        y = v-60
        self._highlightButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(self._width*0.5+bOffs-bSize*0.5,v-50),
                                                    upWidget=self._upgradeButton if self._upgradeButton is not None else self._accountTypeInfoButton,
                                                    size=(bSize,bSize),color=self._highlight,label='',buttonType='square')

        if not self._isAccountProfile and not self._global:
            bs.widget(edit=cancelButton,downWidget=self._textField)
            bs.widget(edit=saveButton,downWidget=self._textField)
            bs.widget(edit=self._colorButton,upWidget=self._textField)
        bs.widget(edit=self._accountTypeInfoButton,downWidget=self._characterButton)
        
        origin = self._highlightButton.getScreenSpaceCenter()
        bs.buttonWidget(edit=self._highlightButton,onActivateCall=bs.WeakCall(self._makePicker,'highlight',origin))
        bs.textWidget(parent=self._rootWidget,hAlign='center',vAlign='center',position=(self._width*0.5+bOffs,v-65),size=(0,0),
                      drawController=b,text=R.highlightText,scale=0.7,color=gTitleColor,maxWidth=120)
        self._updateCharacter()

    def upgradeProfile(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return

        UpgradeProfileWindow(self)
        
    def showAccountProfileInfo(self):
        iconsStr = ' '.join([bs.getSpecialChar(n) for n in ['googlePlusLogo','gameCenterLogo','gameCircleLogo','ouyaLogo','localAccount','alibabaLogo','oculusLogo']])
        txt = bs.getResource('editProfileWindow.accountProfileInfoText').replace('${ICONS}',iconsStr)
        ConfirmWindow(txt, cancelButton=False, width=500, height=300, originWidget=self._accountTypeInfoButton)

    def showLocalProfileInfo(self):
        txt = bs.getResource('editProfileWindow.localProfileInfoText')
        ConfirmWindow(txt, cancelButton=False, width=600, height=250, originWidget=self._accountTypeInfoButton)

    def showGlobalProfileInfo(self):
        txt = bs.getResource('editProfileWindow.globalProfileInfoText')
        ConfirmWindow(txt, cancelButton=False, width=600, height=250, originWidget=self._accountTypeInfoButton)
        
        
    def refreshCharacters(self):
        self._spazzes = bsSpaz.getAppearances()
        self._spazzes.sort()
        self._iconTextures = [bs.getTexture(bsSpaz.appearances[s].iconTexture) for s in self._spazzes]
        self._iconTintTextures = [bs.getTexture(bsSpaz.appearances[s].iconMaskTexture) for s in self._spazzes]

    def onIconPickerPick(self,icon):
        self._icon = icon
        self._updateIcon()
        
    def onCharacterPickerPick(self,character):
        if not self._rootWidget.exists(): return
        self.refreshCharacters() # the player could have bought a new one while the picker was up..
        self._iconIndex = self._spazzes.index(character)
        self._updateCharacter()
        
    def _onCharacterPress(self):
        picker = CharacterPicker(parent=self._rootWidget,position=self._characterButton.getScreenSpaceCenter(),
                                 selectedCharacter=self._spazzes[self._iconIndex],delegate=self,tintColor=self._color,tint2Color=self._highlight)

    def _onIconPress(self):
        picker = IconPicker(parent=self._rootWidget,
                            position=self._iconButton.getScreenSpaceCenter(),
                            selectedIcon=self._icon,
                            delegate=self,
                            tintColor=self._color,
                            tint2Color=self._highlight)
        
    def _makePicker(self,pickerType,origin):
        if pickerType == 'color': initialColor = self._color
        elif pickerType == 'highlight': initialColor = self._highlight
        else: raise Exception("invalid pickerType: "+pickerType)
        self._colorPickers[pickerType] = weakref.ref(ColorPicker(parent=self._rootWidget,position=origin,
                                                                 offset=(self._baseScale*(-100 if pickerType == 'color' else 100),0),
                                                                 initialColor=initialColor,delegate=self))

    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = PlayerProfilesWindow('inLeft',selectedProfile=self._existingProfile,inMainMenu=self._inMainMenu).getRootWidget()

    def _setColor(self,color):
        self._color = color
        if self._colorButton.exists():
            bs.buttonWidget(edit=self._colorButton,color=color)

    def _setHighlight(self,color):
        self._highlight = color
        if self._highlightButton.exists():
            bs.buttonWidget(edit=self._highlightButton,color=color)
        
    def colorPickerClosing(self,picker):
        if not self._rootWidget.exists():
            return
        for pType,pRef in self._colorPickers.items():
            p = pRef()
            if picker == p:
                if pType == 'color':
                    bs.containerWidget(edit=self._rootWidget, selectedChild=self._colorButton)
                elif pType == 'highlight':
                    bs.containerWidget(edit=self._rootWidget, selectedChild=self._highlightButton)

    def colorPickerSelectedColor(self,picker,color):
        for pType,pRef in self._colorPickers.items():
            p = pRef()
            if picker == p:
                if pType == 'color':
                    self._setColor(color)
                elif pType == 'highlight':
                    self._setHighlight(color)
                self._updateCharacter()

    def _updateCharacter(self,change=0):
        self._iconIndex = (self._iconIndex + change)%len(self._spazzes)
        if self._characterButton.exists():
            bs.buttonWidget(edit=self._characterButton,
                            texture=self._iconTextures[self._iconIndex],
                            tintTexture=self._iconTintTextures[self._iconIndex],
                            tintColor=self._color,
                            tint2Color=self._highlight)

    def _updateIcon(self):
        if self._iconButtonLabel.exists():
            bs.textWidget(edit=self._iconButtonLabel,text=self._icon)
        
    def getName(self):
        if self._isAccountProfile:
            newName = '__account__'
        elif self._global:
            newName = self._name
        else:
            newName = bs.textWidget(query=self._textField)
        return newName
    
    def save(self, transitionOut=True):
        bsConfig = bs.getConfig()
        newName = self.getName().strip()
        
        if len(newName) == 0:
            bs.screenMessage(bs.getResource('nameNotEmptyText'))
            bs.playSound(bs.getSound('error'))
            return False
        
        if transitionOut:
            bs.playSound(bs.getSound('gunCocking'))

        # delete old in case we're renaming
        # print 'HAVE',self._existingProfile,type(self._existingProfile),'AND',newName.encode('utf-8'),type(newName)
        if self._existingProfile and self._existingProfile != newName:
            bsInternal._addTransaction({'type':'REMOVE_PLAYER_PROFILE',
                                        'name':self._existingProfile})
            # also lets be aware we're no longer global if we're taking a new name
            # (will need to re-request it)
            self._global = False

        bsInternal._addTransaction({'type':'ADD_PLAYER_PROFILE',
                                    'name':newName,
                                    'profile':{'character':self._spazzes[self._iconIndex],
                                               'color':self._color,
                                               'global':self._global,
                                               'icon':self._icon,
                                               'highlight':self._highlight}})

        if transitionOut:
            bsInternal._runTransactions()
            bs.containerWidget(edit=self._rootWidget,transition='outRight')
            uiGlobals['mainMenuWindow'] = PlayerProfilesWindow('inLeft',selectedProfile=newName,inMainMenu=self._inMainMenu).getRootWidget()
        return True


class PlayerProfilesWindow(Window):

    def __init__(self,transition='inRight',inMainMenu=True,
                 selectedProfile=None,originWidget=None):
        
        self._inMainMenu = inMainMenu
        if self._inMainMenu: backLabel = bs.getResource('backText')
        else: backLabel = bs.getResource('doneText')
        self._width = 600
        self._height = 360 if gSmallUI else 385 if gMedUI else 410
        spacing = 40
        buttonWidth = 350

        # if we're being called up standalone, handle pause/resume ourself
        if not self._inMainMenu:
            pause()
            
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._R = R = bs.getResource('playerProfilesWindow')

        # ensure we've got an account-profile in cases where we're signed in
        bsUtils._ensureHaveAccountPlayerProfile()
        
        # if we're not signed in, issue a warning..
        # if bsInternal._getAccountState() != 'SIGNED_IN':
        #     bs.screenMessage(self._R.signInText,color=(1,0.5,0))
            
        topExtra = 20 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=2.2 if gSmallUI else 1.6 if gMedUI else 1.0,
                                              stackOffset=(0,-14) if gSmallUI else (0,0))

        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(40,self._height-59),size=(120,60),scale=0.8,
                                               label=backLabel,buttonType='back' if backLabel==bs.getResource('backText') else None,
                                               autoSelect=True,
                                               onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-36),size=(0,0),
                          text=R.titleText,maxWidth=300,color=gTitleColor,scale=0.9,hAlign="center",vAlign="center")

        if self._inMainMenu and gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(113,self._height-36))
        
        scrollHeight = self._height - 140
        self._scrollWidth = self._width-188

        #v = self._height - 140
        #v = self._height - 20 - 61 - (scrollHeight-225)*0.5-75
        v = self._height - 84
        h = self._width - 110
        h = 50
        hspacing = 13
        bColor = (0.6,0.53,0.63)

        s = 1.055 if gSmallUI else 1.18 if gMedUI else 1.3
        v -= 70.0*s
        self._newButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(80,66.0*s),
                                              onActivateCall=self._newProfile,
                                              color=bColor,
                                              buttonType='square',
                                              autoSelect=True,
                                              textColor=(0.75,0.7,0.8),
                                              textScale=0.7,
                                              label=R.newButtonText)
        v -= 70.0*s
        self._editButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(80,66.0*s),
                                               onActivateCall=self._editProfile,
                                               color=bColor,
                                               buttonType='square',
                                               autoSelect=True,
                                               textColor=(0.75,0.7,0.8),
                                               textScale=0.7,
                                               label=R.editButtonText)
        v -= 70.0*s
        self._deleteButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(80,66.0*s),
                                                 onActivateCall=self._deleteProfile,
                                                 color=bColor,
                                                 buttonType='square',
                                                 autoSelect=True,
                                                 textColor=(0.75,0.7,0.8),
                                                 textScale=0.7,
                                                 label=R.deleteButtonText)


        v = self._height - 87

        
        # t = bs.textWidget(parent=self._rootWidget,position=(140,self._height-69),size=(0,0),
        #                   text=R.explanationText,
        #                   color=gInfoTextColor,maxWidth=self._scrollWidth,scale=0.6,hAlign="left",vAlign="center")
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-71),size=(0,0),
                          text=R.explanationText,
                          color=gInfoTextColor,maxWidth=self._width*0.83,scale=0.6,hAlign="center",vAlign="center")
        
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,highlight=False,
                                             position=(140,v-scrollHeight),size=(self._scrollWidth,scrollHeight))
        bs.widget(edit=self._scrollWidget,autoSelect=True,leftWidget=self._newButton)
        bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)

        self._columnWidget = bs.columnWidget(parent=self._scrollWidget)
        v -= 255

        self._profiles = None
        self._selectedProfile = selectedProfile
        self._profileWidgets = []


        self._refresh()

        self._restoreState()

    def _newProfile(self):

        # clamp at 100 profiles (otherwise the server will and that's less elegant looking)
        if len(self._profiles) > 100:
            bs.screenMessage(bs.translate('serverResponses','Max number of profiles reached.'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
        
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = EditProfileWindow(existingProfile=None,inMainMenu=self._inMainMenu).getRootWidget()

    def _deleteProfile(self):
        if self._selectedProfile is None:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('nothingIsSelectedErrorText'),color=(1,0,0))
            return
        elif self._selectedProfile == '__account__':
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.cantDeleteAccountProfileText,color=(1,0,0))
            return
        ConfirmWindow(self._R.deleteConfirmText.replace('${PROFILE}',self._selectedProfile),self._doDeleteProfile,350)

    def _doDeleteProfile(self):
        
        # try: del bs.getConfig()['Player Profiles'][self._selectedProfile]
        # except Exception: pass
        # bs.writeConfig()
        bsInternal._addTransaction({'type':'REMOVE_PLAYER_PROFILE',
                                    'name':self._selectedProfile})
        bsInternal._runTransactions()
        
        bs.playSound(bs.getSound('shieldDown'))
        self._refresh()
        bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget) # select profile list

    def _editProfile(self):
        if self._selectedProfile is None:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('nothingIsSelectedErrorText'),color=(1,0,0))
            return
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = EditProfileWindow(self._selectedProfile,inMainMenu=self._inMainMenu).getRootWidget()

    def _select(self,name,index):
        self._selectedProfile = name

    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if self._inMainMenu:
            # uiGlobals['mainMenuWindow'] = SettingsWindow(transition='inLeft').getRootWidget()
            uiGlobals['mainMenuWindow'] = AccountWindow(transition='inLeft').getRootWidget()
        # if we're being called up standalone, handle pause/resume ourself
        else:
            resume()

    def _refresh(self):
        oldSelection = self._selectedProfile
        # delete old
        while len(self._profileWidgets) > 0: self._profileWidgets.pop().delete()
        try: self._profiles = bs.getConfig()['Player Profiles']
        except Exception: self._profiles = {}
        items = self._profiles.items()
        # ensure these are unicode..
        items = [(i[0].decode('utf-8'),i[1]) if type(i[0]) is not unicode else i for i in items]
        items.sort(key=lambda x:x[0].lower())
        index = 0
        accountProfileStr = bs.getResource('editProfileWindow.accountProfileText')
        if bsInternal._getAccountState() == 'SIGNED_IN':
            accountName = bsInternal._getAccountDisplayString()
        else:
            accountName = None
        bsConfig = bs.getConfig()
        widgetToSelect = None
        for pName,p in items:
            # __account__ shouldn't exist when we're not signed in but just in case it does...
            if pName == '__account__' and accountName is None: continue
            color,highlight = bsUtils.getPlayerProfileColors(pName)
            sc = 1.1
            w = bs.textWidget(parent=self._columnWidget,position=(0,32),size=((self._width-40)/sc,28),
                              text=accountName if pName == '__account__' else bsUtils.getPlayerProfileIcon(pName)+pName,
                              hAlign='left',vAlign='center',
                              onSelectCall=bs.WeakCall(self._select,pName,index),
                              maxWidth=self._scrollWidth*0.92,
                              cornerScale=sc,
                              color=bs.getSafeColor(color,0.4),
                              alwaysHighlight=True,
                              onActivateCall=bs.Call(self._editButton.activate),
                              selectable=True)
            if index == 0: bs.widget(edit=w,upWidget=self._backButton)
            bs.widget(edit=w,showBufferTop=40,showBufferBottom=40)
            self._profileWidgets.append(w)

            # select/show this one if it was previously selected
            # (but defer till after this loop since our height is still changing)
            if pName == oldSelection:
                widgetToSelect = w

            index += 1
            
        if widgetToSelect is not None:
            bs.columnWidget(edit=self._columnWidget,selectedChild=widgetToSelect,visibleChild=widgetToSelect)
            
        # if there's a team-chooser in existence, tell it the profile-list has probably changed
        session = bsInternal._getForegroundHostSession()
        if session is not None: session.handleMessage(bsGame.PlayerProfilesChangedMessage())

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._newButton: selName = 'New'
            elif sel == self._editButton: selName = 'Edit'
            elif sel == self._deleteButton: selName = 'Delete'
            elif sel == self._scrollWidget: selName = 'Scroll'
            else: selName = 'Back'
            gWindowStates[self.__class__.__name__] = selName
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]
            except Exception: selName = None
            if selName == 'Scroll': sel = self._scrollWidget
            elif selName == 'New': sel = self._newButton
            elif selName == 'Delete': sel = self._deleteButton
            elif selName == 'Edit': sel = self._editButton
            elif selName == 'Back': sel = self._backButton
            else:
                # by default we select our scroll widget if we have profiles; otherwise our new widget
                if len(self._profileWidgets) == 0: sel = self._newButton
                else: sel = self._scrollWidget
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)

        
class ConfigureWiiRemotesWindow(Window):

    def __init__(self):

        self._R = bs.getResource('wiimoteSetupWindow')
        width = 600
        height = 480
        spacing = 40

        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight')

        b = bs.buttonWidget(parent=self._rootWidget,position=(55,height-50),size=(120,60),scale=0.8,autoSelect=True,
                            label=bs.getResource('backText'),buttonType='back',onActivateCall=self._back)

        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-28),size=(0,0),
                          text=self._R.titleText,
                          maxWidth=270,
                          color=gTitleColor,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(110,height-26))
        
        v = height - 60
        v -= spacing
        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-80),size=(0,0),
                          color=(0.7,0.9,0.7,1.0),
                          scale=self._R.macInstructionsTextScale,
                          text=self._R.macInstructionsText,
                          maxWidth=width*0.95,
                          maxHeight=height*0.5,
                          hAlign="center",vAlign="center")
        v -= 230
        buttonWidth = 200
        v -= 30
        b = bs.buttonWidget(parent=self._rootWidget,position=(width/2-buttonWidth/2,v+1),autoSelect=True,
                            size=(buttonWidth,50),label=self._R.listenText,onActivateCall=WiimoteListenWindow)
        bs.containerWidget(edit=self._rootWidget,startButton=b)
        v -= spacing * 1.1
        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v+10),size=(0,0),
                          color=(0.7,0.9,0.7,1.0),
                          scale=self._R.thanksTextScale,
                          maxWidth=width*0.95,
                          text=self._R.thanksText.strip(),
                          hAlign="center",vAlign="center")
        v -= 30
        thisButtonWidth = 200
        b = bs.buttonWidget(parent=self._rootWidget,position=(width/2-thisButtonWidth/2,v-14),
                            color=(0.45,0.4,0.5),autoSelect=True,
                            size=(thisButtonWidth,15),
                            label=self._R.copyrightText,
                            textColor=(0.55,0.5,0.6),
                            textScale=self._R.copyrightTextScale,
                            onActivateCall=WiimoteLicenseWindow)

    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()


class WiimoteListenWindow(Window):

    def __init__(self):

        self._R = bs.getResource('wiimoteListenWindow')
        width = 650
        height = 210
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight')

        b = bs.buttonWidget(parent=self._rootWidget,position=(35,height-60),size=(140,60),autoSelect=True,
                            label=bs.getResource('cancelText'),scale=0.8,onActivateCall=self._dismiss)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        bsInternal._startListeningForWiiRemotes()
        self._wiimoteConnectCounter = 15

        global dismissWiiRemotesWindow
        dismissWiiRemotesWindow = bs.WeakCall(self._dismiss)

        t = bs.textWidget(parent=self._rootWidget,position=(15,height-55),size=(width-30,30),
                          text=self._R.listeningText,color=gTitleColor,
                          maxWidth=320,
                          hAlign="center",vAlign="center")
        t = bs.textWidget(parent=self._rootWidget,position=(15,height-110),size=(width-30,30),
                          scale=self._R.pressTextScale,
                          text=self._R.pressText,
                          maxWidth=width*0.9,
                          color=(0.7,0.9,0.7,1.0),
                          hAlign="center",vAlign="center")
        t = bs.textWidget(parent=self._rootWidget,position=(15,height-140),size=(width-30,30),
                          color=(0.7,0.9,0.7,1.0),
                          scale=self._R.pressText2Scale,
                          text=self._R.pressText2,
                          maxWidth=width*0.95,
                          hAlign="center",vAlign="center")
        self._counterText = t = bs.textWidget(parent=self._rootWidget,position=(15,23),size=(width-30,30),
                                              scale=1.2,
                                              text=("15"),
                                              hAlign="center",vAlign="top")

        for i in range(1,15):
            bs.realTimer(1000*i,bs.WeakCall(self._decrement))

        bs.realTimer(15000,bs.WeakCall(self._dismiss))

    def _decrement(self):
        try:
            self._wiimoteConnectCounter -= 1
            bs.textWidget(edit=self._counterText,text=str(self._wiimoteConnectCounter))
        except Exception: pass

    def _dismiss(self):
        try:
            bs.containerWidget(edit=self._rootWidget,transition='outLeft')
            bsInternal._stopListeningForWiiRemotes()
        except Exception: pass


class WiimoteLicenseWindow(Window):

    def __init__(self):
        self._R = bs.getResource('wiimoteLicenseWindow')
        width = 750
        height = 550
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight')
        b = bs.buttonWidget(parent=self._rootWidget,position=(65,height-50),size=(120,60),scale=0.8,autoSelect=True,
                            label=bs.getResource('backText'),buttonType='back',onActivateCall=self._close)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(0,height-48),size=(width,30),
                          text=self._R.titleText,hAlign="center",color=gTitleColor,vAlign="center")
        licenseText = ('Copyright (c) 2007, DarwiinRemote Team\n'
                       'All rights reserved.\n'
                       '\n'
                       '   Redistribution and use in source and binary forms, with or without modification,\n'
                       '   are permitted provided that the following conditions are met:\n'
                       '\n'
                       '1. Redistributions of source code must retain the above copyright notice, this\n'
                       '     list of conditions and the following disclaimer.\n'
                       '2. Redistributions in binary form must reproduce the above copyright notice, this\n'
                       '     list of conditions and the following disclaimer in the documentation and/or other\n'
                       '     materials provided with the distribution.\n'
                       '3. Neither the name of this project nor the names of its contributors may be used to\n'
                       '     endorse or promote products derived from this software without specific prior\n'
                       '     written permission.\n'
                       '\n'
                       'THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"\n'
                       'AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE\n'
                       'IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE\n'
                       'ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE\n'
                       'LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR\n'
                       'CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF\n'
                       ' SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS\n'
                       'INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN\n'
                       'CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)\n'
                       'ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE\n'
                       'POSSIBILITY OF SUCH DAMAGE.\n')
        licenseTextScale = 0.62
        t = bs.textWidget(parent=self._rootWidget,position=(100,height*0.45),size=(0,0),
                          hAlign="left",vAlign="center",padding=4,
                          color=(0.7,0.9,0.7,1.0),
                          scale=licenseTextScale,
                          maxWidth=width*0.9-100,maxHeight=height*0.85,
                          text=licenseText)
    def _close(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')


class ConnectPS3ControllersWindow(Window):

    def __init__(self):
        width = 760
        height = 330 if (bsInternal._isOuyaBuild() or bsInternal._isRunningOnFireTV()) else 540
        spacing = 40
        self._R = bs.getResource('ps3ControllersWindow')
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight',
                                              scale=1.35 if gSmallUI else 1.3 if gMedUI else 1.0)

        b = bs.buttonWidget(parent=self._rootWidget,position=(37,height-73),size=(135,65),scale=0.85,
                            label=bs.getResource('backText'),buttonType='back',autoSelect=True,
                            onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-46),size=(0,0),maxWidth=410,
                          text=self._R.titleText.replace('${APP_NAME}',bs.getResource('titleText')),
                          color=gTitleColor,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(90,height-48))
        
        v = height - 90
        v -= spacing

        if bsInternal._isOuyaBuild() or bsInternal._isRunningOnFireTV():
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height*0.45),size=(0,0),
                              color=(0.7,0.9,0.7,1.0),
                              maxWidth=width*0.95,
                              maxHeight=height*0.8,
                              scale=1.0,
                              text=self._R.ouyaInstructionsText,
                              hAlign="center",vAlign="center")
        else:
            txts = self._R.macInstructionsText.split('\n\n\n')
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-29),size=(0,0),
                              color=(0.7,0.9,0.7,1.0),
                              maxWidth=width*0.95,
                              maxHeight=170,
                              scale=1.0,
                              text=txts[0].strip(),
                              hAlign="center",vAlign="center")
            if len(txts) > 0:
                t2 = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-280),size=(0,0),
                                  color=(0.7,0.9,0.7,1.0),
                                  maxWidth=width*0.95,
                                  maxHeight=170,
                                  scale=1.0,
                                  text=txts[1].strip(),
                                  hAlign="center",vAlign="center")
            
            # t = bs.textWidget(parent=self._rootWidget,position=(15,v+15),size=(width-30,30),
            #                   color=(0.7,0.9,0.7,1.0),
            #                   maxWidth=width*0.95,
            #                   scale=self._R.macInstructionsTextScale,
            #                   text=self._R.macInstructionsText,
            #                   hAlign="center",vAlign="top")
            bs.buttonWidget(parent=self._rootWidget,position=(225,v-176),size=(300,40),
                            label=self._R.pairingTutorialText,autoSelect=True,
                            onActivateCall=bs.Call(bs.openURL,'http://www.youtube.com/watch?v=IlR_HxeOQpI&feature=related'))
    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()


class Connect360ControllersWindow(Window):

    def __init__(self):
        self._R = bs.getResource('xbox360ControllersWindow')
        width = 700
        height = 300 if (bsInternal._isOuyaBuild() or bsInternal._isRunningOnFireTV()) else 485
        spacing = 40
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight',scale=1.4 if gSmallUI else 1.4 if gMedUI else 1.0)

        b = bs.buttonWidget(parent=self._rootWidget,position=(35,height-65),size=(120,60),scale=0.84,
                            label=bs.getResource('backText'),buttonType='back',autoSelect=True,
                            onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-42),size=(0,0),scale=0.85,
                          text=self._R.titleText.replace('${APP_NAME}',bs.getResource('titleText')),
                          color=gTitleColor,maxWidth=400,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(90,height-40))
        
        v = height - 70
        v -= spacing

        if bsInternal._isOuyaBuild() or bsInternal._isRunningOnFireTV():
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height*0.47),size=(0,0),
                              color=(0.7,0.9,0.7,1.0),
                              maxWidth=width*0.95,
                              maxHeight=height*0.75,
                              scale=0.7,
                              text=self._R.ouyaInstructionsText,
                              hAlign="center",vAlign="center")
        else:
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-1),size=(0,0),
                              color=(0.7,0.9,0.7,1.0),
                              maxWidth=width*0.95,
                              maxHeight=height*0.22,
                              text=self._R.macInstructionsText,
                              scale=0.7,
                              hAlign="center",vAlign="center")
            v -= 90
            bWidth = 300

            b = bs.buttonWidget(parent=self._rootWidget,position=((width-bWidth)*0.5,v-10),size=(bWidth,50),
                                label=self._R.getDriverText,autoSelect=True,
                                #onActivateCall=bs.Call(bs.openURL,'http://tattiebogle.net/index.php/ProjectRoot/Xbox360Controller/OsxDriver'))
                                onActivateCall=bs.Call(bs.openURL,'https://github.com/d235j/360Controller/releases'))
            bs.containerWidget(edit=self._rootWidget,startButton=b)

            v -= 60
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-85),size=(0,0),
                              color=(0.7,0.9,0.7,1.0),
                              maxWidth=width*0.95,
                              maxHeight=height*0.46,
                              scale=0.7,
                              text=self._R.macInstructions2Text,
                              hAlign="center",vAlign="center")

    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()


class QRCodeWindow(PopupWindow):

    def __init__(self, originWidget, qrTex):

        position=originWidget.getScreenSpaceCenter()
        
        scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        self._transitioningOut = False
        
        self._width = 450
        self._height = 400

        bgColor = (0.5,0.4,0.6)
        
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor)

        env = bs.getEnvironment()

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        bs.imageWidget(parent=self._rootWidget, position=(self._width*0.5-150, self._height*0.5-150), size=(300, 300),
                       texture=qrTex)
        
    def _onCancelPress(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()
        
class ConnectMobileDevicesWindow(Window):

    def __init__(self):

        env = bs.getEnvironment()
        
        # this is different on ali..
        doAli = True if (env['platform'] == 'android' and env['subplatform'] == 'alibaba') else False
        # doAli = True
        
        self._R = bs.getResource('connectMobileDevicesWindow')
        if doAli:
            width = 700
            height = 400
        else:
            width = 700
            height = 390
        spacing = 40
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight',
                                              scale=1.85 if gSmallUI else 1.3 if gMedUI else 1.0,
                                              stackOffset=(-10,0) if gSmallUI else (0,0))
        b = bs.buttonWidget(parent=self._rootWidget,position=(40,height-67),size=(140,65),scale=0.8,
                            label=bs.getResource('backText'),
                            buttonType='back',textScale=1.1,autoSelect=True,
                            onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-42),size=(0,0),
                          text=self._R.titleText,maxWidth=370,
                          color=gTitleColor,scale=0.8,hAlign="center",vAlign="center")

        if doAli:
            t = bs.textWidget(parent=self._rootWidget, position=(width * 0.5, height - 150), size=(0,0),
                              text=('\xe5\xa6\x82\xe9\x9c\x80\xe5\xb0\x86\xe6\x99\xba\xe8\x83\xbd\xe6\x89\x8b\xe6\x9c\xba\xe6\x88\x96\xe5\xb9\xb3\xe6\x9d\xbf\xe7\x94\xb5\xe8\x84\x91\xe7\x94\xa8\xe4\xbd\x9c\xe6\x93\x8d\xe6\x8e\xa7\xe6\x89\x8b\xe6\x9f\x84\xef\xbc\x8c\n'
                                    '\xe8\xaf\xb7\xe5\xae\x89\xe8\xa3\x85\xe4\xbb\xa5\xe4\xb8\x8b\xe5\xba\x94\xe7\x94\xa8\xe4\xb9\x8b\xe4\xb8\x80\xef\xbc\x9a'),
                              maxWidth=width*0.9,
                              color=gTitleColor, scale=1.0, hAlign="center", vAlign="center")

            t = bs.textWidget(parent=self._rootWidget, position=(190, 160), size=(0,0),
                              text='aliTV\xe7\x94\xa8\xe6\x88\xb7',
                              maxWidth=width*0.9,
                              color=gTitleColor, scale=1.1, hAlign="center", vAlign="center")
            b = bs.buttonWidget(parent=self._rootWidget, position=(40,50), size=(300,70), scale=1.0,
                                label=bsUtils._getRemoteAppName(),
                                textScale=1.1,
                                autoSelect=True)
            bs.buttonWidget(edit=b, onActivateCall=bs.Call(QRCodeWindow, b, bs.getTexture('aliControllerQR')))
            t = bs.textWidget(parent=self._rootWidget, position=(width-190, 160), size=(0,0),
                              text='iOS\xe7\x94\xa8\xe6\x88\xb7',
                              maxWidth=width*0.9,
                              color=gTitleColor, scale=1.1, hAlign="center", vAlign="center")
            b = bs.buttonWidget(parent=self._rootWidget, position=(width-340,50), size=(300,70), scale=1.0,
                                label=bs.getResource('remote_app.app_name'),
                                textScale=1.1,
                                autoSelect=True)
            bs.buttonWidget(edit=b, onActivateCall=bs.Call(QRCodeWindow, b, bs.getTexture('aliBSRemoteIOSQR')))
            
            pass
            # bs.imageWidget(parent=self._rootWidget,position=(width*0.5-150,height*0.5-165),size=(300,300),
            #                texture=bs.getTexture('aliControllerQR'))

        else:
            if gDoAndroidNav:
                bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
                bs.textWidget(edit=t,hAlign='left',position=(90,height-44))

            v = height - 70
            v -= spacing*1.2
            t = bs.textWidget(parent=self._rootWidget,position=(15,v-26),size=(width-30,30),
                              maxWidth=width*0.95,
                              color=(0.7,0.9,0.7,1.0),
                              scale=self._R.explanationScale,
                              text=self._R.explanationText.replace('${APP_NAME}',bs.getResource('titleText')).replace('${REMOTE_APP_NAME}',bsUtils._getRemoteAppName()),
                              maxHeight=100,
                              hAlign="center",vAlign="center")
            v -= 100
            bWidth = 200

            # hmm the itms:// version doesnt bounce through safari but is kinda apple-specific-ish
            sep = 230

            # new - just show link to remote page
            if True:
                t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v+5),size=(0,0),
                                  color=(0.7,0.9,0.7,1.0), scale=1.4,
                                  text='bombsquadgame.com/remote',
                                  maxWidth=width*0.95,maxHeight=60,
                                  hAlign="center",vAlign="center")
                v -= 40
                pass
            else:
                if bsInternal._isRunningOnFireTV():
                    t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v+5),size=(0,0),
                                      color=(0.7,0.9,0.7,1.0), scale=0.8,
                                      text=self._R.getItForText.replace('${REMOTE_APP_NAME}',bsUtils._getRemoteAppName()),
                                      maxWidth=width*0.95,maxHeight=60,
                                      hAlign="center",vAlign="center")
                    v -= 40
                else:
                    t = bs.textWidget(parent=self._rootWidget,position=(130,v),size=(0,30),
                                      color=(0.7,0.9,0.7,1.0), scale=0.8,
                                      text=self._R.forIOSText, hAlign="center",vAlign="top")
                    t = bs.textWidget(parent=self._rootWidget,position=(470,v),size=(0,30),
                                      color=(0.7,0.9,0.7,1.0), scale=0.8,
                                      text=self._R.forAndroidText, hAlign="center",vAlign="top")
                    v -= 40

                    b = bs.buttonWidget(parent=self._rootWidget,position=(width*0.5-sep-bWidth*0.5+20,v-10),size=(bWidth*0.94,50),autoSelect=True,
                                        label=self._R.appStoreText, onActivateCall=bs.Call(bs.openURL,'http://appstore.com/bombsquadremote'))
                    env = bs.getEnvironment()

                    # include direct play store link on google android; otherwise give web link
                    if env['platform'] == 'android' and env['subplatform'] == 'google': url = 'market://details?id=net.froemling.bsremote'
                    else: url = 'http://play.google.com/store/apps/details?id=net.froemling.bsremote'

                    b = bs.buttonWidget(parent=self._rootWidget,position=(width*0.5-bWidth*0.5+27,v-10),size=(bWidth*0.89,50),autoSelect=True,
                                        label=self._R.googlePlayText, onActivateCall=bs.Call(bs.openURL,url))
                    b = bs.buttonWidget(parent=self._rootWidget,position=(width*0.5+sep-bWidth*0.5-12,v-10),size=(bWidth*1.0,50),autoSelect=True,
                                        label=self._R.amazonText, onActivateCall=bs.Call(bs.openURL,'http://www.amazon.com/gp/mas/dl/android?p=net.froemling.bsremote'))
                    v -= 32

            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-35),size=(0,0),
                              color=(0.7,0.9,0.7,0.8),
                              scale=self._R.bestResultsScale,
                              text=self._R.bestResultsText,
                              maxWidth=width*0.95,
                              maxHeight=height*0.19,
                              hAlign="center",vAlign="center")

    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()


class ConfigGamePadWindow(Window):

    def __init__(self):
        width = 480
        height = 170
        spacing = 40
        R = bs.getResource('configGamepadSelectWindow')
        self._rootWidget = bs.containerWidget(scale=2.3 if gSmallUI else 1.5 if gMedUI else 1.0,
                                              size=(width,height),transition='inRight')
        b = bs.buttonWidget(parent=self._rootWidget,position=(20,height-60),size=(130,60),
                            label=bs.getResource('backText'),buttonType='back',scale=0.8,
                            onActivateCall=self._back)
        # lets not have anything selected by default; its misleading looking for the controller getting configured..
        bs.containerWidget(edit=self._rootWidget,cancelButton=b,selectedChild=0)
        t = bs.textWidget(parent=self._rootWidget,position=(20,height-50),size=(width,25),text=R.titleText,
                          maxWidth=250,color=gTitleColor,hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(83,height-50))
        
        v = height - 60
        v -= spacing
        t = bs.textWidget(parent=self._rootWidget,position=(15,v),size=(width-30,30),
                          scale=0.8,
                          text=R.pressAnyButtonText,
                          maxWidth=width*0.95,color=gInfoTextColor,hAlign="center",vAlign="top")
        v -= spacing * 1.24
        ua = bs.getEnvironment()['userAgentString']
        if 'android' in ua and not bsInternal._isOuyaBuild() and not bsInternal._isRunningOnFireTV():
            t = bs.textWidget(parent=self._rootWidget,position=(15,v),size=(width-30,30),
                              scale=0.46,
                              text=R.androidNoteText,
                              maxWidth=width*0.95,
                              color=(0.7,0.9,0.7,0.5),
                              hAlign="center",vAlign="top")

        bsInternal._captureGamePadInput(gamePadConfigureCallback)

    def _back(self):
        bsInternal._releaseGamePadInput()
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()


class ConfigTouchscreenWindow(Window):

    def __del__(self):
        # note - this happens in 'back' too just to get it going earlier..
        # (but we do it here too in case somehow the window is closed by another means)
        bsInternal._setTouchscreenEditing(False)

    def __init__(self):

        self._width = 650
        self._height = 380
        self._spacing = 40
        self._R = bs.getResource('configTouchscreenWindow')

        bsInternal._setTouchscreenEditing(True)

        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition='inRight',
                                              scale=1.9 if gSmallUI else 1.55 if gMedUI else 1.2)

        b = bs.buttonWidget(parent=self._rootWidget,position=(55,self._height-60),size=(120,60),
                            label=bs.getResource('backText'),buttonType='back',scale=0.8,
                            onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(25,self._height-50),size=(self._width,25),text=self._R.titleText,
                          color=gTitleColor,maxWidth=280,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(110,self._height-49))
        

        self._scrollWidth = self._width - 100
        self._scrollHeight = self._height - 110
        self._subWidth = self._scrollWidth-20
        self._subHeight = 360

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,
                                             position=((self._width-self._scrollWidth)*0.5,self._height - 65-self._scrollHeight),
                                             size=(self._scrollWidth,self._scrollHeight))
        self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,
                                                    size=(self._subWidth,self._subHeight),
                                                    background=False)
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=self._subContainer,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)

        self._buildGui()

    def _buildGui(self):

        # clear anything already there
        #children = bs.getWidgetChildren(self._rootWidget)
        children = self._subContainer.getChildren()
        for c in children: c.delete()
        
        h = 30
        v = self._subHeight - 85

        cl = (0.8,0.8,0.8,1.0)
        cl2 = (0.8,0.8,0.8)

        bs.textWidget(parent=self._subContainer,position=(-10,v+43),size=(self._subWidth,25),
                      text=self._R.swipeInfoText,flatness=1.0,
                      color=(0,0.9,0.1,0.7),maxWidth=self._subWidth*0.9,
                      scale=0.55,hAlign="center",vAlign="center")

        try: curVal = bs.getConfig()['Touch Movement Control Type']
        except Exception: curVal = 'swipe'
        bs.textWidget(parent=self._subContainer,position=(h,v-2),size=(0,30),
                      text=self._R.movementText,maxWidth=190,color=cl,vAlign='center')
        c1 = bs.checkBoxWidget(parent=self._subContainer,position=(h+220,v),size=(170,30),
                               text=self._R.joystickText,maxWidth=100,textColor=cl2,scale=0.9)
        c2 = bs.checkBoxWidget(parent=self._subContainer,position=(h+357,v),size=(170,30),
                               text=self._R.swipeText,maxWidth=100,textColor=cl2,value=0,scale=0.9)
        _makeRadioGroup((c1,c2),('joystick','swipe'),curVal,self._movementChanged)

        v -= 50
        configTextBox(parent=self._subContainer,position=(h,v),xOffset=65,name="Touch Controls Scale Movement",displayName=self._R.movementControlScaleText,
                      type="float",changeSound=False,minVal=0.1,maxVal=4.0,increment=0.1)
        
        v -= 50

        try: curVal = bs.getConfig()['Touch Action Control Type']
        except Exception: curVal = 'buttons'
        bs.textWidget(parent=self._subContainer,position=(h,v-2),size=(0,30),
                      text=self._R.actionsText,maxWidth=190,color=cl,vAlign='center')
        c1 = bs.checkBoxWidget(parent=self._subContainer,position=(h+220,v),size=(170,30),
                               text=self._R.buttonsText,maxWidth=100,textColor=cl2,scale=0.9)
        c2 = bs.checkBoxWidget(parent=self._subContainer,position=(h+357,v),size=(170,30),
                               text=self._R.swipeText,maxWidth=100,textColor=cl2,scale=0.9)
        _makeRadioGroup((c1,c2),('buttons','swipe'),curVal,self._actionsChanged)


        v -= 50
        configTextBox(parent=self._subContainer,position=(h,v),xOffset=65,name="Touch Controls Scale Actions",displayName=self._R.actionControlScaleText,
                      type="float",changeSound=False,minVal=0.1,maxVal=4.0,increment=0.1)

        v -= 50
        configCheckBox(parent=self._subContainer,position=(h,v),
                       size=(400,30),maxWidth=400,name="Touch Controls Swipe Hidden",displayName=self._R.swipeControlsHiddenText)
        
        v -= 65

        b = bs.buttonWidget(parent=self._subContainer,position=(self._subWidth*0.5-70,v),size=(170,60),
                            label=self._R.resetText,scale=0.75,onActivateCall=self._reset)

        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,38),size=(0,0),hAlign='center',
                          text=self._R.dragControlsText,maxWidth=self._width*0.8,
                          scale=0.65,color=(1,1,1,0.4))
        

    def _actionsChanged(self,v):
        bs.getConfig()['Touch Action Control Type'] = v
        bs.writeConfig()
        bs.applySettings()

    def _movementChanged(self,v):
        bs.getConfig()['Touch Movement Control Type'] = v
        bs.writeConfig()
        bs.applySettings()

    def _reset(self):
        bsConfig = bs.getConfig()
        prefs = ['Touch Movement Control Type',
                 'Touch Action Control Type',
                 'Touch Controls Scale',
                 'Touch Controls Scale Movement',
                 'Touch Controls Scale Actions',
                 'Touch Controls Swipe Hidden',
                 'Touch DPad X',
                 'Touch DPad Y',
                 'Touch Buttons X',
                 'Touch Buttons Y']
        for p in prefs:
            if p in bsConfig:
                del(bsConfig[p])

        bs.writeConfig()
        bs.applySettings()

        bs.realTimer(0,self._buildGui)


    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()
        bsInternal._setTouchscreenEditing(False)


def gamePadConfigureCallback(event):

    # ignore all but button-presses
    if event['type'] not in ['BUTTONDOWN','HATMOTION']: return

    bsInternal._releaseGamePadInput()

    try: bs.containerWidget(edit=uiGlobals['mainMenuWindow'],transition='outLeft')
    except Exception:
        bs.printException("error transitioning out mainMenuWindow")
    bs.playSound(bs.getSound('activateBeep'))
    bs.playSound(bs.getSound('swish'))
    if event['inputDevice']._getAllowsConfiguring():
        uiGlobals['mainMenuWindow'] = GamePadConfigWindow(event["inputDevice"]).getRootWidget()
    else:
        width = 700
        height = 200
        buttonWidth = 100
        uiGlobals['mainMenuWindow'] = d = bs.containerWidget(scale=1.7 if gSmallUI else 1.4 if gMedUI else 1.0,
                                                             size=(width,height),transition='inRight')
        deviceName = event['inputDevice'].getName()
        if deviceName == 'iDevice':
            msg = bs.getResource('bsRemoteConfigureInAppText').replace('${REMOTE_APP_NAME}',bsUtils._getRemoteAppName())
        else:
            msg = bs.getResource('cantConfigureDeviceText').replace('${DEVICE}',deviceName)
        t = bs.textWidget(parent=d,position=(0,height-80),size=(width,25),
                          text=msg,
                          scale=0.8,
                          hAlign="center",vAlign="top")
        def _ok():
            bs.containerWidget(edit=d,transition='outRight')
            uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()
        b = bs.buttonWidget(parent=d,position=((width-buttonWidth)/2,20),size=(buttonWidth,60),label=bs.getResource('okText'),onActivateCall=_ok)


class AwaitGamePadInputWindow(Window):

    def __init__(self,gamePad,button,callback,message=None,message2=None):

        if message is None:
            print 'AwaitGamePadInputWindow message is None!'
            message = 'Press any button...' # shouldnt get here
            
        self._callback = callback
        self._input = gamePad
        self._captureButton = button

        width = 400
        height = 150
        self._rootWidget = bs.containerWidget(scale=2.0 if gSmallUI else 1.9 if gMedUI else 1.0,
                                              size=(width,height),transition='inScale')
        t = bs.textWidget(parent=self._rootWidget,position=(0,(height-60) if message2 is None else (height-50)),
                          size=(width,25),text=message,maxWidth=width*0.9,
                          hAlign="center",vAlign="center")
        if message2 is not None:
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-60),size=(0,0),text=message2,maxWidth=width*0.9,
                              scale=0.47,color=(0.7,1.0,0.7,0.6),hAlign="center",vAlign="center")
        self._counter = 5
        self._countDownText = bs.textWidget(parent=self._rootWidget,hAlign='center',position=(0,height-110),size=(width,25),color=(1,1,1,0.3),text=str(self._counter));
        self._decrementTimer = bs.Timer(1000,bs.Call(self._decrement),repeat=True,timeType='real')
        bsInternal._captureGamePadInput(bs.WeakCall(self._eventCallback))

    def __del__(self):
        pass

    def die(self):
        self._decrementTimer = None # this strong-refs us; killing it allow us to die now
        bsInternal._releaseGamePadInput()
        if self._rootWidget.exists():
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
    def _eventCallback(self,event):
        match = (event["inputDevice"] == self._input)

        # update - we now allow *any* input device of this type
        try:
            if event['inputDevice'].getName() == self._input.getName(): match = True
        except Exception as e:
            # seems somewhat common for devices to disappear during this;
            # report any *other* errors..
            if 'Nonexistant input device' not in str(e):
                bs.printException('AwaitGamePadInputWindow: error comparing input devices')

        if match: self._callback(self._captureButton,event,self)

    def _decrement(self):
        self._counter -= 1
        if (self._counter >= 1):
            if self._countDownText.exists():
                bs.textWidget(edit=self._countDownText,text=str(self._counter))
        else:
            bs.playSound(bs.getSound('error'))
            self.die()

        
class AwaitKeyboardInputWindow(Window):

    def __init__(self,button,ui,settings):

        self._captureButton = button
        self._captureKeyUI=ui
        self._settings = settings

        width = 400
        height = 150
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight')
        t = bs.textWidget(parent=self._rootWidget,position=(0,height-60),size=(width,25),text=bs.getResource('pressAnyKeyText'),
                          hAlign="center",vAlign="top")

        self._counter = 5
        self._countDownText = bs.textWidget(parent=self._rootWidget,hAlign='center',position=(0,height-110),size=(width,25),color=(1,1,1,0.3),text=str(self._counter));
        self._decrementTimer = bs.Timer(1000,bs.Call(self._decrement),repeat=True,timeType='real')
        bsInternal._captureKeyboardInput(bs.WeakCall(self._buttonCallback))

    def __del__(self):
        bsInternal._releaseKeyboardInput()

    def _die(self):
        self._decrementTimer = None # this strong-refs us; killing it allow us to die now
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        
    def _buttonCallback(self,event):
        self._settings[self._captureButton] = event["button"]
        if event['type'] == 'BUTTONDOWN':
            t = event['inputDevice'].getButtonName(event["button"])
            bs.textWidget(edit=self._captureKeyUI,text=t)
            bs.playSound(bs.getSound('gunCocking'))
            self._die()

    def _decrement(self):
        self._counter -= 1
        if (self._counter >= 1):
            bs.textWidget(edit=self._countDownText,text=str(self._counter))
        else:
            self._die()

# class PurchaseProgressWindow(Window):

#     def __init__(self):
#         # print 'PurchaseProgressWindow()'

#         width = 400
#         height = 150
#         bs.playSound(bs.getSound('swish'))
#         self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight',
#                                               scale=2.0 if gSmallUI else 1.5 if gMedUI else 1.0)
#         self._txt = bs.getResource('purchasingText')
#         self._statusTextWidget = bs.textWidget(parent=self._rootWidget,position=(width*0.5-bs.getStringWidth(self._txt)*0.5,height*0.5),size=(0,0),
#                                                color=gInfoTextColor,
#                                                text=self._txt,
#                                                hAlign="left",vAlign="center")
#         #self._counter = 5
#         #self._countDownText = bs.textWidget(parent=self._rootWidget,hAlign='center',position=(0,height-110),size=(width,25),color=(1,1,1,0.3),text=str(self._counter));

#         # kill ourself eventually just in case something goes wrong..
#         #self._dieTimer = bs.Timer(5000,bs.WeakCall(self.die),repeat=False,timeType='real')
#         self._statusTextWidgetUpdateTimer = bs.Timer(500,bs.WeakCall(self._updateStatusText),repeat=True,timeType='real')
#         self._statusTextDots = 1

#     def _updateStatusText(self):
#         #print 'updating status text'
#         if self._statusTextWidget.exists():
#             bs.textWidget(edit=self._statusTextWidget,
#                           text=self._txt+'.'*self._statusTextDots)
#             self._statusTextDots += 1
#             if self._statusTextDots > 3:
#                 self._statusTextDots = 0

#     # def __del__(self):
#     #     print '~PurchaseProgressWindow()'

#     def die(self):
#         bs.playSound(bs.getSound('swish'))
#         #self._decrementTimer = None # this strong-refs us; killing it allow us to die now
#         bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        
#     # def _decrement(self):
#     #     self._counter -= 1
#     #     if (self._counter >= 1):
#     #         bs.textWidget(edit=self._countDownText,text=str(self._counter))
#     #     else:
#     #         self.die()


# given an input-device and button name, returns the currently configured button ID
def getControllerValue(c,button,exceptionOnUnknown=False):

    name = c.getName()
    uniqueID = c.getUniqueIdentifier()
    env = bs.getEnvironment()
    ua = env['userAgentString']
    platform = env['platform']
    subplatform = env['subplatform']
    
    bsConfig = bs.getConfig()
    
    if (bsConfig.has_key("Controllers")):
        jsconfig = bsConfig["Controllers"]
        if (jsconfig.has_key(name)):
            src = None
            if (jsconfig[name].has_key(uniqueID)):
                src = jsconfig[name][uniqueID]
            elif (jsconfig[name].has_key("default")):
                src = jsconfig[name]["default"]
            if (src is not None):
                if (src.has_key(button)):
                    return src[button]
                else: return -1

    # print 'TEMP RETURNING NO DEFAULTS'
    # if exceptionOnUnknown: raise Exception()
    # else: return -1
        

    if platform == 'windows':
        
        # XInput (hopefully this mapping is consistent?...)
        if name.startswith('XInput Controller'):
            try: return {'triggerRun2': 3, 'unassignedButtonsRun': False, 'buttonPickUp': 4, 'buttonBomb': 2, 'buttonStart': 8, 'buttonIgnored2': 7,
                         'triggerRun1': 6, 'buttonPunch': 3, 'buttonRun2': 5, 'buttonRun1': 6, 'buttonJump': 1, 'buttonIgnored': 11}[button]
            except Exception: return -1

        # ps4 controller
        if name == 'Wireless Controller':
            try: return {'triggerRun2': 4, 'unassignedButtonsRun': False, 'buttonPickUp': 4, 'buttonBomb': 3, 'buttonJump': 2,
                         'buttonStart': 10, 'buttonPunch': 1, 'buttonRun2': 5, 'buttonRun1': 6, 'triggerRun1': 5}[button]
            except Exception: return -1
            
    # look for some exact types..
    if bsInternal._isRunningOnFireTV():
        if name in ['Thunder','Amazon Fire Game Controller']:
            try: return {'triggerRun2': 23, 'unassignedButtonsRun': False, 'buttonPickUp': 101, 'buttonBomb': 98,
                         'buttonJump': 97, 'analogStickDeadZone': 0.0, 'startButtonActivatesDefaultWidget': False,
                         'buttonStart': 83, 'buttonPunch': 100, 'buttonRun2': 103, 'buttonRun1': 104, 'triggerRun1': 24}[button]
            except Exception: return -1
        elif name == 'NYKO PLAYPAD PRO':
            try: return {'triggerRun2': 23, 'triggerRun1': 24, 'buttonPickUp': 101, 'buttonBomb': 98, 'buttonJump': 97,
                         'buttonUp': 20, 'buttonLeft': 22, 'buttonRight': 23, 'buttonStart': 83, 'buttonPunch': 100, 'buttonDown': 21}[button]
            except Exception: return -1
        elif name == 'Logitech Dual Action':
            try: return {'triggerRun2': 23, 'triggerRun1': 24, 'buttonPickUp': 98, 'buttonBomb': 101,
                         'buttonJump': 100, 'buttonStart': 109, 'buttonPunch': 97}[button]
            except Exception: return -1
        elif name == 'Xbox 360 Wireless Receiver':
            try: return {'triggerRun2': 23, 'triggerRun1': 24, 'buttonPickUp': 101, 'buttonBomb': 98, 'buttonJump': 97, 'buttonUp': 20,
                         'buttonLeft': 22, 'buttonRight': 23, 'buttonStart': 83, 'buttonPunch': 100, 'buttonDown': 21}[button]
            except Exception: return -1
        elif name == 'Microsoft X-Box 360 pad':
            try: return {'triggerRun2': 23, 'triggerRun1': 24, 'buttonPickUp': 101, 'buttonBomb': 98, 'buttonJump': 97, 'buttonStart': 83,
                         'buttonPunch': 100}[button]
            except Exception: return -1
        elif name in ['Amazon Remote','Amazon Bluetooth Dev','Amazon Fire TV Remote']:
            try: return {'triggerRun2': 23, 'triggerRun1': 24, 'buttonPickUp': 24, 'buttonBomb': 91,
                         'buttonJump': 86, 'buttonUp': 20, 'buttonLeft': 22, 'startButtonActivatesDefaultWidget': False,
                         'buttonRight': 23, 'buttonStart': 83, 'buttonPunch': 90, 'buttonDown': 21}[button]
            except Exception: return -1

    if 'OUYA' in ua:
        if name == 'Generic X-Box pad':
            try: return {
                'analogStickDeadZone':1.2,'buttonBomb':98,'buttonIgnored':111,'buttonJump':97,'buttonPickUp':101,
                'buttonPunch':100,'buttonStart':109,'triggerRun1':12,'triggerRun2':15}[button]
            except Exception: return -1
        elif name == 'Logitech Dual Action':
            try: return {'buttonBomb':98,'buttonJump':97,'buttonPickUp':101,'buttonPunch':100,'buttonStart':109}[button]
            except Exception: return -1
        elif name == 'Microsoft X-Box 360 pad':
            try: return {'analogStickDeadZone':1.2,'buttonBomb':98,'buttonIgnored':83,'buttonJump':97,'buttonPickUp':101,
                         'buttonPunch':100,'buttonStart':109,'triggerRun1':18,'triggerRun2':19}[button]
            except Exception: return -1
        elif name == 'OUYA Game Controller':
            try: return {'triggerRun2': 18, 'unassignedButtonsRun': False, 'buttonPickUp': 101, 'buttonBomb': 98,
                         'buttonJump': 97, 'analogStickDeadZone': 1.2, 'buttonLeft': 22, 'buttonUp': 20,
                         'startButtonActivatesDefaultWidget': False, 'buttonRight': 23, 'buttonStart': 83, 'buttonDown': 21, 'buttonPunch': 100, 'buttonRun2': 103,
                         'buttonRun1': 104, 'triggerRun1': 19, 'autoRecalibrateAnalogStick': True}[button]
            except Exception: return -1
        elif name == 'PLAYSTATION(R)3 Controller':
            try: return {'buttonBomb':98,'buttonDown':21,'buttonIgnored':83,'buttonJump':97,'buttonLeft':22,
                         'buttonPickUp':101,'buttonPunch':100,'buttonRight':23,'buttonStart':109,'buttonUp':20}[button]
            except Exception: return -1
        elif name == 'Sony PLAYSTATION(R)3 Controller':
            try: return {'buttonPickUp': 101, 'buttonBomb': 98, 'buttonJump': 97, 'buttonUp': 20, 'buttonLeft': 22,
                        'buttonRight': 23, 'buttonStart': 109, 'buttonPunch': 100, 'buttonDown': 21, 'buttonIgnored': 83}[button]
            except Exception: return -1
        elif name == 'Xbox 360 Wireless Receiver':
            try: return {'analogStickDeadZone':1.2,'buttonBomb':98,'buttonDown':21,'buttonIgnored':83,
                         'buttonJump':97,'buttonLeft':22,'buttonPickUp':101,'buttonPunch':100,
                         'buttonRight':23,'buttonStart':109,'buttonUp':20,'triggerRun1':18,'triggerRun2':19}[button]
            except Exception: return -1

    elif 'NVIDIA SHIELD;' in ua:
        if 'NVIDIA Controller' in name:
            try: return {'triggerRun2': 19, 'triggerRun1': 18, 'buttonPickUp': 101, 'buttonBomb': 98, 'buttonJump': 97,
                         'analogStickDeadZone': 0.0, 'buttonStart': 109, 'buttonPunch': 100, 'buttonIgnored':184,
                         'buttonIgnored2':86}[button]
            except Exception: return -1

    elif 'Mac' in ua:
        if name == 'PLAYSTATION(R)3 Controller': # ps3 gamepad
            try: return  {'buttonLeft':8,'buttonUp':5,'buttonRight':6,'buttonDown':7,'buttonJump':15,'buttonPunch':16,'buttonBomb':14,'buttonPickUp':13,'buttonStart':4,'buttonIgnored':17}[button]
            except Exception: pass
        if name == 'Wireless 360 Controller' or name == 'Controller': # xbox360 gamepads
            try: return  {'analogStickDeadZone':1.2,'buttonBomb':13,'buttonDown':2,'buttonJump':12,'buttonLeft':3,
                          'buttonPickUp':15,'buttonPunch':14,'buttonRight':4,'buttonStart':5,
                          'buttonUp':1,'triggerRun1':5,'triggerRun2':6,'buttonIgnored':11}[button]
            except Exception: return -1
        if name in ['Logitech Dual Action','Logitech Cordless RumblePad 2']:
            try: return  {'buttonJump':2,'buttonPunch':1,'buttonBomb':3,'buttonPickUp':4,'buttonStart':10}[button]
            except Exception: return -1
        if name == 'GamePad Pro USB ' : # old gravis gamepad
            try: return  {'buttonJump':2,'buttonPunch':1,'buttonBomb':3,'buttonPickUp':4,'buttonStart':10}[button]
            except Exception: return -1
        if name == 'Microsoft SideWinder Plug & Play Game Pad':
            try: return  {'buttonJump':1,'buttonPunch':3,'buttonBomb':2,'buttonPickUp':4,'buttonStart':6}[button]
            except Exception: return -1
        if name == 'Saitek P2500 Rumble Force Pad': # Saitek P2500 Rumble Force Pad.. (hopefully works for others too?..)
            try: return  {'buttonJump':3,'buttonPunch':1,'buttonBomb':4,'buttonPickUp':2,'buttonStart':11}[button]
            except Exception: return -1
        if name == 'Twin USB Joystick': # some crazy 'Senze' dual gamepad (the second half is handled under the hood)
            try: return  {'analogStickLR':3,'analogStickLR_B':7,'analogStickUD':4,'analogStickUD_B':8,'buttonBomb':2,'buttonBomb_B':14,
                          'buttonJump':3,'buttonJump_B':15,'buttonPickUp':1,'buttonPickUp_B':13,'buttonPunch':4,'buttonPunch_B':16,'buttonRun1':7,
                          'buttonRun1_B':19,'buttonRun2':8,'buttonRun2_B':20,'buttonStart':10,'buttonStart_B':22,'enableSecondary':1,'unassignedButtonsRun':False}[button]
            except Exception: return -1
        if name == 'USB Gamepad ': # some weird 'JITE' gamepad
            try: return  {'analogStickLR':4,'analogStickUD':5,'buttonJump':3,'buttonPunch':4,'buttonBomb':2,'buttonPickUp':1,'buttonStart':10}[button]
            except Exception: return -1

    defaultAndroidMapping = {'triggerRun2': 19, 'unassignedButtonsRun': False, 'buttonPickUp': 101,
                             'buttonBomb': 98, 'buttonJump': 97, 'buttonStart': 83, 'buttonStart2':109,
                             'buttonPunch': 100, 'buttonRun2': 104, 'buttonRun1': 103, 'triggerRun1': 18,
                             'buttonLeft':22, 'buttonRight':23, 'buttonUp':20, 'buttonDown':21, 'buttonVRReorient':110}

    # generic android...
    if platform == 'android':

        # steelseries stratus xl
        if name == 'SteelSeries Stratus XL':
            try: return {'triggerRun2': 23, 'unassignedButtonsRun': False, 'buttonPickUp': 101,
                         'buttonBomb': 98, 'buttonJump': 97, 'buttonStart': 83, 'buttonStart2':109,
                         'buttonPunch': 100, 'buttonRun2': 104, 'buttonRun1': 103, 'triggerRun1': 24,
                         'buttonLeft':22, 'buttonRight':23, 'buttonUp':20, 'buttonDown':21, 'buttonVRReorient':108}[button]
            except Exception: return -1
        
        # adt-1 gamepad (use funky 'mode' button for start)
        if name == 'Gamepad':
            try: return {'triggerRun2': 19, 'unassignedButtonsRun': False, 'buttonPickUp': 101,
                         'buttonBomb': 98, 'buttonJump': 97, 'buttonStart': 111, 'buttonPunch': 100,
                         'startButtonActivatesDefaultWidget':False,
                         'buttonRun2': 104, 'buttonRun1': 103, 'triggerRun1': 18}[button]
            except Exception: return -1
        # nexus player remote
        if name == 'Nexus Remote':
            try: return {'triggerRun2': 19, 'unassignedButtonsRun': False, 'buttonPickUp': 101,
                         'buttonBomb': 98, 'buttonJump': 97, 'buttonUp': 20, 'buttonLeft': 22,
                         'buttonDown': 21, 'buttonRight': 23, 'buttonStart': 83, 'buttonStart2': 109,
                         'buttonPunch': 24, 'buttonRun2': 104, 'buttonRun1': 103, 'triggerRun1': 18}[button]
            except Exception: return -1

        if name == "virtual-remote":
            try: return {'triggerRun2': 19, 'unassignedButtonsRun': False, 'buttonPickUp': 101, 'buttonBomb': 98,
                         'buttonStart': 83, 'buttonJump': 24, 'buttonUp': 20, 'buttonLeft': 22, 'buttonRight': 23,
                         'triggerRun1': 18, 'buttonStart2': 109, 'buttonPunch': 100, 'buttonRun2': 104, 'buttonRun1': 103,
                         'buttonDown': 21, 'startButtonActivatesDefaultWidget': False, 'uiOnly': True}[button]
            except Exception: return -1

        # flag particular gamepads to use exact android defaults..
        # (so they don't even ask to configure themselves)
        if name in ['Samsung Game Pad EI-GP20', 'ASUS Gamepad'] or name.startswith('Freefly VR Glide'):
            try: return defaultAndroidMapping[button]
            except Exception: return -1

        # nvidia controller is default, but gets some strange keypresses we want to ignore..
        # touching the touchpad, so lets ignore those.
        if 'NVIDIA Controller' in name:
            try: return {'triggerRun2': 19, 'unassignedButtonsRun': False, 'buttonPickUp': 101,
                         'buttonIgnored':126,'buttonIgnored2':1,
                         'buttonBomb': 98, 'buttonJump': 97, 'buttonStart': 83, 'buttonStart2':109,
                         'buttonPunch': 100, 'buttonRun2': 104, 'buttonRun1': 103, 'triggerRun1': 18}[button]
            except Exception: return -1

        # ali box controller
        if name.startswith('alitv-Vgamepad'):
            try: return {'triggerRun2': 23, 'unassignedButtonsRun': False, 'buttonPickUp': 101, 'buttonBomb': 98,
                         'buttonJump': 97, 'buttonStart': 109, 'buttonStart2': 109, 'buttonPunch': 100,
                         'buttonRun2': 104, 'buttonRun1': 103, 'triggerRun1': 24,
                         'buttonLeft':22, 'buttonRight':23, 'buttonUp':20, 'buttonDown':21
            }[button]
            except Exception: return -1

        # ali remotes
        if name.startswith('ALITV RC_MIC') or name.startswith('sun6i-ir'):
            try: return {'triggerRun2': 19, 'unassignedButtonsRun': False, 'buttonPickUp': 101, 'buttonBomb': 98,
                         'buttonStart': 83, 'buttonJump': 24, 'buttonUp': 20, 'buttonLeft': 22, 'buttonRight': 23,
                         'triggerRun1': 18, 'buttonStart2': 109, 'buttonPunch': 100, 'buttonRun2': 104, 'buttonRun1': 103,
                         'buttonDown': 21, 'startButtonActivatesDefaultWidget': False,'uiOnly': True, 'buttonIgnored':142, 'buttonIgnored2':143}[button]
            except Exception: return -1

            
    # default keyboard vals across platforms..
    if name == 'Keyboard' and uniqueID == '#2':
        try: return  {'buttonJump':258,'buttonPunch':257,'buttonBomb':262,'buttonPickUp':261,'buttonUp':273,'buttonDown':274,'buttonLeft':276,'buttonRight':275,'buttonStart':263}[button]
        except Exception: pass
    if name == 'Keyboard' and uniqueID == '#1':
        try: return {'buttonJump':107,'buttonPunch':106,'buttonBomb':111,'buttonPickUp':105,'buttonUp':119,'buttonDown':115,'buttonLeft':97,'buttonRight':100}[button]
        except Exception: pass

    # ok, this gamepad's not in our specific preset list; at this point let's error if requested to,
    # otherwise lets try some good guesses based on known types...
    if exceptionOnUnknown: raise Exception("Unknown controller type")

    # leaving these in here for now but not gonna add any more now that we have
    # fancy-pants config sharing across the internet...
    if 'Mac' in ua:
        if 'PLAYSTATION' in name: # ps3 gamepad?..
            try: return  {'buttonLeft':8,'buttonUp':5,'buttonRight':6,'buttonDown':7,'buttonJump':15,'buttonPunch':16,'buttonBomb':14,'buttonPickUp':13,'buttonStart':4}[button]
            except Exception: pass
        if 'Logitech' in name: # Dual Action Config - hopefully applies to more...
            try: return  {'buttonJump':2,'buttonPunch':1,'buttonBomb':3,'buttonPickUp':4,'buttonStart':10}[button]
            except Exception: pass
        if 'Saitek' in name: # Saitek P2500 Rumble Force Pad.. (hopefully works for others too?..)
            try: return  {'buttonJump':3,'buttonPunch':1,'buttonBomb':4,'buttonPickUp':2,'buttonStart':11}[button]
            except Exception: pass
        if 'GamePad' in name: # gravis stuff?...
            try: return  {'buttonJump':2,'buttonPunch':1,'buttonBomb':3,'buttonPickUp':4,'buttonStart':10}[button]
            except Exception: pass

    # reasonable defaults..
    if platform == 'android':
        if bsInternal._isRunningOnFireTV():
            # mostly same as default firetv controller..
            try: return {'triggerRun2': 23, 'triggerRun1': 24, 'buttonPickUp': 101, 'buttonBomb': 98,
                         'buttonJump': 97, 'buttonStart': 83, 'buttonPunch': 100,
                         'buttonDown': 21, 'buttonUp': 20, 'buttonLeft': 22, 'buttonRight': 23,
                         'startButtonActivatesDefaultWidget': False,}[button]
            except Exception: return -1
        else:

            # mostly same as 'Gamepad' except with 'menu' for default start button instead of 'mode'
            try: return defaultAndroidMapping[button]
            except Exception: return -1
    else:
        try: return {'buttonJump':1,'buttonPunch':2,'buttonBomb':3,'buttonPickUp':4,'buttonStart':5}[button]
        except Exception: pass

    # epic fail.
    return -1



class GamePadConfigWindow(Window):

    def __init__(self,gamePad,isMainMenu=True,transition='inRight',transitionOut='outRight',settings=None):

        self._input = gamePad

        # if this fails, our input device went away or something.. just return an empty zombie then
        try: self._name = self._input.getName()
        except Exception: return

        self._R = bs.getResource('configGamepadWindow')

        self._settings = settings
        self._transitionOut = transitionOut

        # we're a secondary gamepad if supplied with settings
        self._isSecondary = (settings is not None)
        self._ext = '_B' if self._isSecondary else ''
        self._isMainMenu = isMainMenu
        self._displayName = self._name
        buttonWidth = 240
        self._width = 700 if self._isSecondary else 730
        self._height = 440 if self._isSecondary else 450
        self._spacing = 40
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              scale=1.63 if gSmallUI else 1.35 if gMedUI else 1.0,
                                              stackOffset=(0,-16) if gSmallUI else (0,0),
                                              transition=transition)
        # dont ask to config joysticks while we're in here..
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = False

        self._rebuildUI()


    def _rebuildUI(self):

        # clear existing UI
        #for w in bs.getWidgetChildren(self._rootWidget): w.delete()
        for w in self._rootWidget.getChildren(): w.delete()

        self._textWidgets = {}

        # if we were supplied with settings, we're a secondary joystick and just operate on that.
        # in the other (normal) case we make our own..
        if not self._isSecondary:

            # fill our temp config with present values (for our primary and secondary controls)
            self._settings = {}
            for s in ['buttonJump','buttonJump_B',
                      'buttonPunch','buttonPunch_B',
                      'buttonBomb','buttonBomb_B',
                      'buttonPickUp','buttonPickUp_B',
                      'buttonStart','buttonStart_B',
                      'buttonStart2','buttonStart2_B',
                      'buttonUp','buttonUp_B',
                      'buttonDown','buttonDown_B',
                      'buttonLeft','buttonLeft_B',
                      'buttonRight','buttonRight_B',
                      'buttonRun1','buttonRun1_B',
                      'buttonRun2','buttonRun2_B',
                      'triggerRun1','triggerRun1_B',
                      'triggerRun2','triggerRun2_B',
                      'buttonIgnored','buttonIgnored_B',
                      'buttonIgnored2','buttonIgnored2_B',
                      'buttonIgnored3','buttonIgnored3_B',
                      'buttonIgnored4','buttonIgnored4_B',
                      'buttonVRReorient','buttonVRReorient_B',
                      'analogStickDeadZone','analogStickDeadZone_B',
                      'dpad','dpad_B',
                      'unassignedButtonsRun','unassignedButtonsRun_B',
                      'startButtonActivatesDefaultWidget','startButtonActivatesDefaultWidget_B',
                      'uiOnly','uiOnly_B',
                      'ignoreCompletely','ignoreCompletely_B',
                      'autoRecalibrateAnalogStick','autoRecalibrateAnalogStick_B',
                      'analogStickLR','analogStickLR_B',
                      'analogStickUD','analogStickUD_B',
                      'enableSecondary',]:
                val = getControllerValue(self._input,s)
                if val != -1: self._settings[s] = val

        #if not self._isSecondary:
        if self._isSecondary:
            backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-180,self._height-65),autoSelect=True,
                                             size=(160,60),label=bs.getResource('doneText'),scale=0.9,
                                             onActivateCall=self._save)
            # backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(51,self._height-65),autoSelect=True,
            #                                  size=(160,60),label=bs.getResource('backText'),scale=0.9,
            #                                  buttonType='back',onActivateCall=self._save)
            #bs.containerWidget(edit=self._rootWidget,cancelButton=backButton)
            bs.containerWidget(edit=self._rootWidget,startButton=backButton,onCancelCall=backButton.activate)
            cancelButton = None
        else:
            cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(51,self._height-65),autoSelect=True,
                                               size=(160,60),label=bs.getResource('cancelText'),scale=0.9,
                                               onActivateCall=self._cancel)
            bs.containerWidget(edit=self._rootWidget,cancelButton=cancelButton)
            backButton = None
        #else: cancelButton = None

        if not self._isSecondary:
            saveButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-(165 if self._isSecondary else 195),self._height-65),
                                             size=((160 if self._isSecondary else 180),60),autoSelect=True,
                                             label=bs.getResource('doneText') if self._isSecondary else bs.getResource('makeItSoText'),
                                             scale=0.9,
                                             onActivateCall=self._save)
            bs.containerWidget(edit=self._rootWidget,startButton=saveButton)
        else: saveButton = None

        if not self._isSecondary:

            v = self._height - 59
            t = bs.textWidget(parent=self._rootWidget,position=(0,v+5),size=(self._width,25),
                              text=self._R.titleText,
                              color=gTitleColor,maxWidth=310,
                              hAlign="center",vAlign="center")
            v -= 48

            t = bs.textWidget(parent=self._rootWidget,position=(0,v+3),size=(self._width,25),text=self._name,
                              color=gInfoTextColor,maxWidth=self._width*0.9,
                              hAlign="center",vAlign="center")

            v -= self._spacing * 1

            bs.textWidget(parent=self._rootWidget,position=(50,v+10),size=(self._width-100,30),
                          text=self._R.appliesToAllText,maxWidth=330,
                          scale=0.65, color=(0.5,0.6,0.5,1.0),hAlign='center',vAlign='center')
            v -= 70
            self._enableCheckBox = None
        else:
            v = self._height - 49
            t = bs.textWidget(parent=self._rootWidget,position=(0,v+5),size=(self._width,25),text=self._R.secondaryText,
                              color=gTitleColor,maxWidth=300,hAlign="center",vAlign="center")
            v -= self._spacing * 1

            bs.textWidget(parent=self._rootWidget,position=(50,v+10),size=(self._width-100,30),
                          text=self._R.secondHalfText,
                          maxWidth=300,scale=0.65, color=(0.6,0.8,0.6,1.0),hAlign='center')
            self._enableCheckBox = bs.checkBoxWidget(parent=self._rootWidget,position=(self._width*0.5-80,v-73),
                                                     value=self._getEnableSecondaryValue(),
                                                     autoSelect=True,
                                                     onValueChangeCall=self._enableCheckBoxChanged,
                                                     size=(200,30),text=self._R.secondaryEnableText,scale=1.2)
            v = self._height - 205

        hOffs = 160
        dist = 70

        dColor = (0.4,0.4,0.8)

        sx = 1.2
        sy = 0.98

        dpm = self._R.pressAnyButtonOrDpadText
        dpm2 = self._R.ifNothingHappensTryAnalogText
        bLTop = self._captureButton(pos=(hOffs,v+sy*dist),color=dColor,button='buttonUp'+self._ext,texture=bs.getTexture('upButton'),scale=1.0,message=dpm,message2=dpm2)
        bLLeft = self._captureButton(pos=(hOffs-sx*dist,v),color=dColor,button='buttonLeft'+self._ext,texture=bs.getTexture('leftButton'),scale=1.0,message=dpm,message2=dpm2)
        bLRight = self._captureButton(pos=(hOffs+sx*dist,v),color=dColor,button='buttonRight'+self._ext,texture=bs.getTexture('rightButton'),scale=1.0,message=dpm,message2=dpm2)
        bLBottom = self._captureButton(pos=(hOffs,v-sy*dist),color=dColor,button='buttonDown'+self._ext,texture=bs.getTexture('downButton'),scale=1.0,message=dpm,message2=dpm2)

        dpm3 = self._R.ifNothingHappensTryDpadText
        bAxes = self._captureButton(pos=(hOffs+130,v-125),color=(0.4,0.4,0.6),button='analogStickLR'+self._ext,maxWidth=140,
                            texture=bs.getTexture('analogStick'),scale=1.2,message=self._R.pressLeftRightText,message2=dpm3)

        bStart = self._captureButton(pos=(self._width*0.5,v),color=(0.4,0.4,0.6),button='buttonStart'+self._ext,texture=bs.getTexture('startButton'),scale=0.7)

        hOffs = self._width-160

        bRTop = self._captureButton(pos=(hOffs,v+sy*dist),color=(0.6,0.4,0.8),button='buttonPickUp'+self._ext,texture=bs.getTexture('buttonPickUp'),scale=1.0)
        bRLeft = self._captureButton(pos=(hOffs-sx*dist,v),color=(0.7,0.5,0.1),button='buttonPunch'+self._ext,texture=bs.getTexture('buttonPunch'),scale=1.0)
        bRRight = self._captureButton(pos=(hOffs+sx*dist,v),color=(0.5,0.2,0.1),button='buttonBomb'+self._ext,texture=bs.getTexture('buttonBomb'),scale=1.0)
        bRBottom = self._captureButton(pos=(hOffs,v-sy*dist),color=(0.2,0.5,0.2),button='buttonJump'+self._ext,texture=bs.getTexture('buttonJump'),scale=1.0)

        self._advancedButton = bAdvanced = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label=self._R.advancedText,textScale=0.9,color=(0.45,0.4,0.5),
                                                           textColor=(0.65,0.6,0.7),position=(self._width-300,30),size=(130,40),onActivateCall=self._doAdvanced)

        try:
            if cancelButton is not None and saveButton is not None:
                bs.widget(edit=cancelButton,rightWidget=saveButton)
                bs.widget(edit=saveButton,leftWidget=cancelButton)
        except Exception:
            bs.printException('error wiring gamepad config window')
            
    def _doAdvanced(self):

        class _AdvancedWindow(Window):

            def __init__(self,parentWindow,transition='inRight'):
                self._parentWindow = parentWindow

                env = bs.getEnvironment()
                
                self._R = parentWindow._R
                self._width = 700
                self._height = 442 if gSmallUI else 512
                self._textWidgets = {}
                self._rootWidget = bs.containerWidget(transition='inScale',size=(self._width,self._height),
                                                      scale=1.06*(1.85 if gSmallUI else 1.35 if gMedUI else 1.0),
                                                      stackOffset=(0,-25) if gSmallUI else (0,0),
                                                      scaleOriginStackOffset=(parentWindow._advancedButton.getScreenSpaceCenter()))

                t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-(40 if gSmallUI else 34)),size=(0,0),
                                  text=self._R.advancedTitleText,
                                  maxWidth=320,color=gTitleColor,hAlign="center",vAlign="center")

                backButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(self._width-176,self._height-(60 if gSmallUI else 55)),
                                                 size=(120,48),textScale=0.8,
                                                 label=bs.getResource('doneText'),onActivateCall=self._done)
                bs.containerWidget(edit=self._rootWidget,startButton=b,onCancelCall=b.activate)


                self._scrollWidth = self._width - 100
                self._scrollHeight = self._height - 110
                self._subWidth = self._scrollWidth-20
                self._subHeight = 940 if self._parentWindow._isSecondary else 1040
                if env['vrMode']: self._subHeight += 50
                self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,
                                                     position=((self._width-self._scrollWidth)*0.5,self._height - 65-self._scrollHeight),
                                                     size=(self._scrollWidth,self._scrollHeight))
                self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,
                                                            size=(self._subWidth,self._subHeight),background=False)
                bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
                bs.containerWidget(edit=self._subContainer,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)
                
                h = 30
                v = self._subHeight - 10

                h2 = h + 12
                
                # dont allow secondary joysticks to handle unassigned buttons
                if not self._parentWindow._isSecondary:
                    v -= 40
                    c1 = bs.checkBoxWidget(parent=self._subContainer,position=(h+70,v),size=(500,30),
                                           text=self._R.unassignedButtonsRunText,textColor=(0.8,0.8,0.8),maxWidth=330,
                                           scale=1.0,onValueChangeCall=self._parentWindow._setUnassignedButtonsRunValue,
                                           autoSelect=True,
                                           value=self._parentWindow._getUnassignedButtonsRunValue())
                    bs.widget(edit=c1,upWidget=backButton)
                v -= 60
                cb = self._captureButton(pos=(h2,v),name=self._R.runButton1Text,control='buttonRun1'+self._parentWindow._ext)
                if self._parentWindow._isSecondary:
                    for w in cb: bs.widget(edit=w,upWidget=backButton)
                v -= 42
                self._captureButton(pos=(h2,v),name=self._R.runButton2Text,control='buttonRun2'+self._parentWindow._ext)
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-24),size=(0,0),
                              text=self._R.runTriggerDescriptionText,
                              color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                              scale=0.7,hAlign='center',vAlign='center')

                v -= 85
                
                self._captureButton(pos=(h2,v),name=self._R.runTrigger1Text,
                                    control='triggerRun1'+self._parentWindow._ext,
                                    message=self._R.pressAnyAnalogTriggerText)
                v -= 42
                self._captureButton(pos=(h2,v),name=self._R.runTrigger2Text,
                                    control='triggerRun2'+self._parentWindow._ext,
                                    message=self._R.pressAnyAnalogTriggerText)

                # in vr mode, allow assigning a reset-view button
                if env['vrMode']:
                    v -= 50
                    self._captureButton(pos=(h2,v),name=self._R.vrReorientButtonText,control='buttonVRReorient'+self._parentWindow._ext)
                    
                # bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-16),size=(0,0),
                #               text=self._R.runTriggerDescriptionText,
                #               color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                #               scale=0.7,hAlign='center',vAlign='center')
                v -= 60
                self._captureButton(pos=(h2,v),name=self._R.extraStartButtonText,control='buttonStart2'+self._parentWindow._ext)
                v -= 60
                self._captureButton(pos=(h2,v),name=self._R.ignoredButton1Text,control='buttonIgnored'+self._parentWindow._ext)
                v -= 42
                self._captureButton(pos=(h2,v),name=self._R.ignoredButton2Text,control='buttonIgnored2'+self._parentWindow._ext)
                v -= 42
                self._captureButton(pos=(h2,v),name=self._R.ignoredButton3Text,control='buttonIgnored3'+self._parentWindow._ext)
                v -= 42
                self._captureButton(pos=(h2,v),name=self._R.ignoredButton4Text,control='buttonIgnored4'+self._parentWindow._ext)
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-14),size=(0,0),
                              text=self._R.ignoredButtonDescriptionText,
                              color=(0.7,1,0.7,0.6),
                              scale=0.8,maxWidth=self._subWidth*0.8,
                              hAlign='center',vAlign='center')

                v -= 80
                c1 = bs.checkBoxWidget(parent=self._subContainer,autoSelect=True,position=(h+50,v),size=(400,30),
                                       text=self._R.startButtonActivatesDefaultText,
                                       textColor=(0.8,0.8,0.8),maxWidth=450,
                                       scale=0.9,onValueChangeCall=self._parentWindow._setStartButtonActivatesDefaultWidgetValue,
                                       value=self._parentWindow._getStartButtonActivatesDefaultWidgetValue())
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-12),size=(0,0),
                              text=self._R.startButtonActivatesDefaultDescriptionText,
                              color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                              scale=0.7,hAlign='center',vAlign='center')

                v -= 80
                c1 = bs.checkBoxWidget(parent=self._subContainer,autoSelect=True,position=(h+50,v),size=(400,30),
                                       text=self._R.uiOnlyText,
                                       textColor=(0.8,0.8,0.8),maxWidth=450,
                                       scale=0.9,onValueChangeCall=self._parentWindow._setUIOnlyValue,
                                       value=self._parentWindow._getUIOnlyValue())
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-12),size=(0,0),
                              text=self._R.uiOnlyDescriptionText,
                              color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                              scale=0.7,hAlign='center',vAlign='center')

                v -= 80
                c1 = bs.checkBoxWidget(parent=self._subContainer,autoSelect=True,position=(h+50,v),size=(400,30),
                                       text=self._R.ignoreCompletelyText,
                                       textColor=(0.8,0.8,0.8),maxWidth=450,
                                       scale=0.9,onValueChangeCall=self._parentWindow._setIgnoreCompletelyValue,
                                       value=self._parentWindow._getIgnoreCompletelyValue())
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-12),size=(0,0),
                              text=self._R.ignoreCompletelyDescriptionText,
                              color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                              scale=0.7,hAlign='center',vAlign='center')
                
                v -= 80

                c1 = bs.checkBoxWidget(parent=self._subContainer,autoSelect=True,position=(h+50,v),size=(400,30),
                                       text=self._R.autoRecalibrateText,textColor=(0.8,0.8,0.8),maxWidth=450,
                                       scale=0.9,onValueChangeCall=self._parentWindow._setAutoRecalibrateAnalogStickValue,
                                       value=self._parentWindow._getAutoRecalibrateAnalogStickValue())
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-12),size=(0,0),
                              text=self._R.autoRecalibrateDescriptionText,
                              color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                              scale=0.7,hAlign='center',vAlign='center')
                v -= 80

                buttons = self._configValueEditor(self._R.analogStickDeadZoneText,control='analogStickDeadZone'+self._parentWindow._ext,
                                                  position=(h+40,v),minVal=0,maxVal=10.0,increment=0.1,xOffset=100)
                bs.widget(edit=buttons[0],leftWidget=c1,upWidget=c1)
                bs.widget(edit=c1,rightWidget=buttons[0],downWidget=buttons[0])
                
                bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-12),size=(0,0),
                              text=self._R.analogStickDeadZoneDescriptionText,
                              color=(0.7,1,0.7,0.6),maxWidth=self._subWidth*0.8,
                              scale=0.7,hAlign='center',vAlign='center')
                v -= 100
                
                # child joysticks cant have child joysticks.. that's just crazy talk
                if not self._parentWindow._isSecondary:
                    bs.buttonWidget(parent=self._subContainer,autoSelect=True,label=self._R.twoInOneSetupText,
                                    position=(40,v),size=(self._subWidth-80,50),onActivateCall=self._parentWindow._showSecondaryEditor,upWidget=buttons[0])

                # set a bigger bottom show-buffer for the widgets we just made so we can see the text below them when navigating
                # with a gamepad
                for w in self._subContainer.getChildren():
                    bs.widget(edit=w,showBufferBottom=30,showBufferTop=30)

            def _captureButton(self,pos,name,control,message=self._R.pressAnyButtonText):
                b = bs.buttonWidget(parent=self._subContainer,autoSelect=True,position=(pos[0],pos[1]),
                                    label=name,size=(250,60),scale=0.7)
                b2 = bs.buttonWidget(parent=self._subContainer,autoSelect=True,position=(pos[0]+400,pos[1]+2),
                                     leftWidget=b,
                                     color=(0.45,0.4,0.5),textColor=(0.65,0.6,0.7),
                                     label=self._R.clearText,size=(110,50),scale=0.7,
                                     onActivateCall=bs.Call(self._clearControl,control))
                bs.widget(edit=b,rightWidget=b2)
                # make this in a timer so that it shows up on top of all other buttons
                def foo():
                    t = bs.textWidget(parent=self._subContainer,position=(pos[0]+285,pos[1]+20),
                                      color=(1,1,1,0.3),size=(0,0),hAlign='center',vAlign='center',scale=0.7,
                                      text=self._parentWindow._getControlValueName(control),
                                      maxWidth=200)
                    self._textWidgets[control] = t
                    bs.buttonWidget(edit=b,onActivateCall=bs.Call(AwaitGamePadInputWindow,self._parentWindow._input,control,self._gamePadEvent,message))
                bs.realTimer(0,foo)
                return [b,b2]


            def _inc(self,control,minVal,maxVal,inc):
                try: val = self._parentWindow._settings[control]
                except Exception: val = 1.0
                val = min(maxVal,max(minVal,val+inc))
                if abs(1.0-val) < 0.001:
                    if control in self._parentWindow._settings: del(self._parentWindow._settings[control])
                else: self._parentWindow._settings[control] = round(val,1)
                bs.textWidget(edit=self._textWidgets[control],text=self._parentWindow._getControlValueName(control))

            def _configValueEditor(self,name,control,position,type='float',minVal=0,maxVal=100,increment=1.0,callback=None,changeSound=True,xOffset=0,displayName=None,textScale=1.0):

                if displayName is None: displayName = name
                t = bs.textWidget(parent=self._subContainer,position=position,size=(100,30),text=displayName,
                                  color=(0.8,0.8,0.8,1.0),hAlign="left",vAlign="center",scale=1.0,maxWidth=280)
                if type == 'string':
                    raise Exception("fixme unimplemented");
                else:
                    self._textWidgets[control] = t = bs.textWidget(parent=self._subContainer,position=(246+xOffset,position[1]),
                                                                   size=(60,28),editable=False,
                                                                   color=(0.3,1.0,0.3,1.0),hAlign="right",vAlign="center",
                                                                   text=self._parentWindow._getControlValueName(control),padding=2)
                    b = bs.buttonWidget(parent=self._subContainer,autoSelect=True,position=(330+xOffset,position[1]+4),size=(28,28),label="-",
                                        onActivateCall=bs.Call(self._inc,control,minVal,maxVal,-increment),
                                        repeat=True,enableSound=(changeSound is True))
                    b2 = bs.buttonWidget(parent=self._subContainer,autoSelect=True,position=(380+xOffset,position[1]+4),size=(28,28),label="+",
                                        onActivateCall=bs.Call(self._inc,control,minVal,maxVal,increment),
                                        repeat=True,enableSound=(changeSound is True))
                    return (b,b2)

            def _clearControl(self,control):
                e = self._parentWindow._ext
                if control in self._parentWindow._settings: del(self._parentWindow._settings[control])
                bs.textWidget(edit=self._textWidgets[control],text=self._parentWindow._getControlValueName(control))

            def _gamePadEvent(self,control,event,dialog):
                e = self._parentWindow._ext
                if control in ['triggerRun1'+e,'triggerRun2'+e]:
                    if event['type'] == 'AXISMOTION':
                        # ignore small values or else we might get triggered by noise
                        if abs(event['value']) > 0.5:
                            self._parentWindow._settings[control] = event['axis']
                            # update the button's text widget
                            bs.textWidget(edit=self._textWidgets[control],text=self._parentWindow._getControlValueName(control))
                            bs.playSound(bs.getSound('gunCocking'))
                            dialog.die()
                else:
                    if event['type'] == 'BUTTONDOWN':
                        value = event['button']
                        self._parentWindow._settings[control] = value
                        # update the button's text widget
                        bs.textWidget(edit=self._textWidgets[control],text=self._parentWindow._getControlValueName(control))
                        bs.playSound(bs.getSound('gunCocking'))
                        dialog.die()

            def _done(self):
                bs.containerWidget(edit=self._rootWidget,transition='outScale')

        w = _AdvancedWindow(self)

    def _enableCheckBoxChanged(self,value):
        if value: self._settings['enableSecondary'] = 1
        else:
            if 'enableSecondary' in self._settings: del self._settings['enableSecondary']

    def _getUnassignedButtonsRunValue(self):
        if 'unassignedButtonsRun' in self._settings: return self._settings['unassignedButtonsRun']
        else: return True
    def _setUnassignedButtonsRunValue(self,value):
        if value:
            if 'unassignedButtonsRun' in self._settings:
                del(self._settings['unassignedButtonsRun']) # clear since this is default
        else: self._settings['unassignedButtonsRun'] = False

    def _getStartButtonActivatesDefaultWidgetValue(self):
        if 'startButtonActivatesDefaultWidget' in self._settings:
            return self._settings['startButtonActivatesDefaultWidget']
        else:
            return True

    def _setStartButtonActivatesDefaultWidgetValue(self,value):
        if value:
            if 'startButtonActivatesDefaultWidget' in self._settings:
                del(self._settings['startButtonActivatesDefaultWidget']) # clear since this is default
        else: self._settings['startButtonActivatesDefaultWidget'] = False

    def _getUIOnlyValue(self):
        if 'uiOnly' in self._settings:
            return self._settings['uiOnly']
        else:
            return False

    def _setUIOnlyValue(self,value):
        if not value:
            if 'uiOnly' in self._settings:
                del(self._settings['uiOnly']) # clear since this is default
        else: self._settings['uiOnly'] = True

    def _getIgnoreCompletelyValue(self):
        if 'ignoreCompletely' in self._settings:
            return self._settings['ignoreCompletely']
        else:
            return False

    def _setIgnoreCompletelyValue(self,value):
        if not value:
            if 'ignoreCompletely' in self._settings:
                del(self._settings['ignoreCompletely']) # clear since this is default
        else: self._settings['ignoreCompletely'] = True
        
    def _getAutoRecalibrateAnalogStickValue(self):
        if 'autoRecalibrateAnalogStick' in self._settings: return self._settings['autoRecalibrateAnalogStick']
        else: return False

    def _setAutoRecalibrateAnalogStickValue(self,value):
        if not value:
            if 'autoRecalibrateAnalogStick' in self._settings:
                del(self._settings['autoRecalibrateAnalogStick']) # clear since this is default
        else: self._settings['autoRecalibrateAnalogStick'] = True

    def _getEnableSecondaryValue(self):
        if not self._isSecondary: raise Exception("enable value only applies to secondary editor")
        if 'enableSecondary' in self._settings: return self._settings['enableSecondary']
        else: return False

    def _showSecondaryEditor(self):
        GamePadConfigWindow(self._input,isMainMenu=False,settings=self._settings,transition='inScale',transitionOut='outScale')

    def _getControlValueName(self,control):

        if control == 'analogStickLR'+self._ext:
            # this actually shows both LR and UD
            s1 = self._settings['analogStickLR'+self._ext] if 'analogStickLR'+self._ext in self._settings else 5 if self._isSecondary else 1
            s2 = self._settings['analogStickUD'+self._ext] if 'analogStickUD'+self._ext in self._settings else 6 if self._isSecondary else 2
            #return self._R.axisText+' '+s1+' & '+s2
            return self._input.getAxisName(s1)+' / '+self._input.getAxisName(s2)

        # if they're looking for triggers
        if control in ['triggerRun1'+self._ext,'triggerRun2'+self._ext]:
            if control in self._settings: return self._input.getAxisName(self._settings[control])
            else: return self._R.unsetText
            #return (self._R.axisText+' '+str(self._settings[control])) if control in self._settings else self._R.unsetText
            
        # dead-zone
        if control == 'analogStickDeadZone'+self._ext:
            if control in self._settings: return str(self._settings[control])
            else: return str(1.0)

        # for dpad buttons: show individual buttons if any are set..
        # otherwise show whichever dpad is set (defaulting to 1)
        dPadButtons = ['buttonLeft'+self._ext,'buttonRight'+self._ext,'buttonUp'+self._ext,'buttonDown'+self._ext]
        if control in dPadButtons:
            # if *any* dpad buttons are assigned, show only button assignments
            if any(b in self._settings for b in dPadButtons):
                if control in self._settings:
                    return self._input.getButtonName(self._settings[control])
                else: return self._R.unsetText
            # no dpad buttons - show the dpad number for all 4
            else:
                return self._R.dpadText+' '+str(self._settings['dpad'+self._ext] if 'dpad'+self._ext in self._settings else 2 if self._isSecondary else 1)

        # other buttons..
        if control in self._settings:
            return self._input.getButtonName(self._settings[control])
        else: return self._R.unsetText

    def _gamePadEvent(self,control,event,dialog):
        e = self._ext
        # for our dpad-buttons we're looking for either a button-press or a hat-switch press
        if control in ['buttonUp'+e, 'buttonLeft'+e, 'buttonDown'+e, 'buttonRight'+e]:
            if event['type'] in ['BUTTONDOWN', 'HATMOTION']:
                # if its a button-down..
                if event['type'] == 'BUTTONDOWN':
                    value = event['button']
                    self._settings[control] = value
                # if its a dpad
                elif event['type'] == 'HATMOTION':
                    # clear out any set dir-buttons
                    for b in ['buttonUp'+e,'buttonLeft'+e,'buttonRight'+e,'buttonDown'+e]:
                        if b in self._settings: del(self._settings[b])
                    if event['hat'] == (2 if self._isSecondary else 1): # exclude value in default case
                        if 'dpad'+e in self._settings: del(self._settings['dpad'+e])
                    else: self._settings['dpad'+e] = event['hat']
                # update the 4 dpad button txt widgets
                bs.textWidget(edit=self._textWidgets['buttonUp'+e],text=self._getControlValueName('buttonUp'+e))
                bs.textWidget(edit=self._textWidgets['buttonLeft'+e],text=self._getControlValueName('buttonLeft'+e))
                bs.textWidget(edit=self._textWidgets['buttonRight'+e],text=self._getControlValueName('buttonRight'+e))
                bs.textWidget(edit=self._textWidgets['buttonDown'+e],text=self._getControlValueName('buttonDown'+e))
                bs.playSound(bs.getSound('gunCocking'))
                dialog.die()

        elif control == 'analogStickLR'+e:
            if event['type'] == 'AXISMOTION':
                # ignore small values or else we might get triggered by noise
                if abs(event['value']) > 0.5:
                    axis = event['axis']
                    if axis == (5 if self._isSecondary else 1): # exclude value in default case
                        if 'analogStickLR'+e in self._settings: del(self._settings['analogStickLR'+e])
                    else: self._settings['analogStickLR'+e] = axis
                    bs.textWidget(edit=self._textWidgets['analogStickLR'+e],text=self._getControlValueName('analogStickLR'+e))
                    bs.playSound(bs.getSound('gunCocking'))
                    dialog.die()
                    # now launch the up/down waiter
                    AwaitGamePadInputWindow(self._input,'analogStickUD'+e,self._gamePadEvent,self._R.pressUpDownText)

        elif control == 'analogStickUD'+e:
            if event['type'] == 'AXISMOTION':
                # ignore small values or else we might get triggered by noise
                if abs(event['value']) > 0.5:
                    axis = event['axis']
                    # ignore our LR axis
                    if 'analogStickLR'+e in self._settings: lrAxis = self._settings['analogStickLR'+e]
                    else: lrAxis = (5 if self._isSecondary else 1)
                    if axis != lrAxis:
                        if axis == (6 if self._isSecondary else 2): # exclude value in default case
                            if 'analogStickUD'+e in self._settings: del(self._settings['analogStickUD'+e])
                        else: self._settings['analogStickUD'+e] = axis
                        bs.textWidget(edit=self._textWidgets['analogStickLR'+e],text=self._getControlValueName('analogStickLR'+e))
                        #print 'WOULD CHANGE TXT'
                        bs.playSound(bs.getSound('gunCocking'))
                        dialog.die()
        else:
            # for other buttons we just want a button-press
            if event['type'] == 'BUTTONDOWN':
                value = event['button']
                self._settings[control] = value
                # update the button's text widget
                bs.textWidget(edit=self._textWidgets[control],text=self._getControlValueName(control))
                bs.playSound(bs.getSound('gunCocking'))
                dialog.die()

    def _captureButton(self,pos,color,texture,button,scale=1.0,message=None,message2=None,maxWidth=80):
        if message is None: message = self._R.pressAnyButtonText

        baseSize = 79
        b = bs.buttonWidget(parent=self._rootWidget,position=(pos[0]-baseSize*0.5*scale,pos[1]-baseSize*0.5*scale),
                            autoSelect=True,size=(baseSize*scale,baseSize*scale),
                            texture=texture,label='',color=color)
        # make this in a timer so that it shows up on top of all other buttons
        def foo():
            uiScale = 0.9*scale
            t = bs.textWidget(parent=self._rootWidget,position=(pos[0]+0.0*scale,pos[1]-58.0*scale),
                              color=(1,1,1,0.3),size=(0,0),hAlign='center',vAlign='center',
                              scale=uiScale, text=self._getControlValueName(button),maxWidth=maxWidth)
            self._textWidgets[button] = t
            bs.buttonWidget(edit=b,onActivateCall=bs.Call(AwaitGamePadInputWindow,self._input,button,self._gamePadEvent,message,message2))

        bs.realTimer(0,foo)
        return b
    
    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if self._isMainMenu:
            uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = True

    def _save(self):

        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)

        # if we're a secondary editor we just go away (we were editing our parent's settings dict)
        if self._isSecondary: return

        if self._input.exists():
            dst = getConfigLocationForInputDevice(self._input,default=True)
            dst = dst[0][dst[1]]
            dst.clear()
            # store any values that aren't -1
            for key,val in self._settings.items():
                if val != -1: dst[key] = val
            # if we're allowed to phone home, send this config so we can generate more defaults in the future
            if bsUtils._shouldSubmitDebugInfo():
                bsUtils.serverPut('controllerConfig',{'ua':bs.getEnvironment()['userAgentString'],'name':self._name,'inputMapHash':getInputMapHash(self._input),'config':dst,'v':2})
            bs.applySettings()
            bs.writeConfig()
            bs.playSound(bs.getSound('gunCocking'))
        else:
            bs.playSound(bs.getSound('error'))
            
        if self._isMainMenu:
            uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = True


class ConfigKeyboardWindow(Window):


    def __init__(self,c,transition='inRight'):

        self._R = bs.getResource('configKeyboardWindow')
        self._input = c
        self._name = self._input.getName()
        self._uniqueID = self._input.getUniqueIdentifier()
        self._displayName = self._name
        if self._uniqueID != '#1': self._displayName += ' '+self._uniqueID.replace('#','P')
        self._displayName = bs.translate('inputDeviceNames',self._displayName)
        buttonWidth = 240
        self._width = 700
        if self._uniqueID != "#1": self._height = 450
        else: self._height = 345
        self._spacing = 40
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              scale=1.6 if gSmallUI else 1.3 if gMedUI else 1.0,
                                              stackOffset=(0,-10) if gSmallUI else (0,0),
                                              transition=transition)

        # dont ask to config joysticks while we're in here..
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = False

        self._rebuildUI()


    def _rebuildUI(self):

        for w in self._rootWidget.getChildren():
            w.delete()

        # fill our temp config with present values
        self._settings = {}
        for button in ['buttonJump','buttonPunch','buttonBomb','buttonPickUp',
                       'buttonStart','buttonStart2','buttonUp','buttonDown','buttonLeft','buttonRight']:
            self._settings[button] = getControllerValue(self._input,button)

        cancelButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(38,self._height-65),size=(170,60),label=bs.getResource('cancelText'),scale=0.9,onActivateCall=self._cancel);
        saveButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(self._width-190,self._height-65),size=(180,60),label=bs.getResource('makeItSoText'),scale=0.9,textScale=0.9,onActivateCall=self._save)
        bs.containerWidget(edit=self._rootWidget,cancelButton=cancelButton,startButton=saveButton)

        bs.widget(edit=cancelButton,rightWidget=saveButton)
        bs.widget(edit=saveButton,leftWidget=cancelButton)
        
        v = self._height - 54
        t = bs.textWidget(parent=self._rootWidget,
                          position=(self._width*0.5,v+15),
                          size=(0,0),
                          text=bs.uni(self._R.configuringText).replace('${DEVICE}',self._displayName),
                          color=gTitleColor,
                          hAlign='center',vAlign='center',maxWidth=270,
                          scale=0.83)
        # t = bs.textWidget(parent=self._rootWidget,position=(-10,v),size=(self._width,25),text="Configuring " + self._displayName,color=gTitleColor,
        #                   scale=0.83,hAlign="center",vAlign="top")
        v -= 20

        if self._uniqueID != "#1":
            v -= 20
            v -= self._spacing
            t = bs.textWidget(parent=self._rootWidget,position=(0,v+19),size=(self._width,50),
                              text=self._R.keyboard2NoteText,
                              scale=self._R.keyboard2NoteScale,
                              maxWidth=self._width*0.75,
                              maxHeight=110,
                              color=gInfoTextColor,
                              hAlign="center",vAlign="top")
            v -= 45
        v -= 10
        v -= self._spacing * 2.2

        v += 25
        v -= 42

        hOffs = 160
        dist = 70

        dColor = (0.4,0.4,0.8)
        self._captureButton(pos=(hOffs,v+0.95*dist),color=dColor,button='buttonUp',texture=bs.getTexture('upButton'),scale=1.0)
        self._captureButton(pos=(hOffs-1.2*dist,v),color=dColor,button='buttonLeft',texture=bs.getTexture('leftButton'),scale=1.0)
        self._captureButton(pos=(hOffs+1.2*dist,v),color=dColor,button='buttonRight',texture=bs.getTexture('rightButton'),scale=1.0)
        self._captureButton(pos=(hOffs,v-0.95*dist),color=dColor,button='buttonDown',texture=bs.getTexture('downButton'),scale=1.0)

        if self._uniqueID == "#2":
            self._captureButton(pos=(self._width*0.5,v+0.1*dist),color=(0.4,0.4,0.6),button='buttonStart',texture=bs.getTexture('startButton'),scale=0.8)

        hOffs = self._width-160

        self._captureButton(pos=(hOffs,v+0.95*dist),color=(0.6,0.4,0.8),button='buttonPickUp',texture=bs.getTexture('buttonPickUp'),scale=1.0)
        self._captureButton(pos=(hOffs-1.2*dist,v),color=(0.7,0.5,0.1),button='buttonPunch',texture=bs.getTexture('buttonPunch'),scale=1.0)
        self._captureButton(pos=(hOffs+1.2*dist,v),color=(0.5,0.2,0.1),button='buttonBomb',texture=bs.getTexture('buttonBomb'),scale=1.0)
        self._captureButton(pos=(hOffs,v-0.95*dist),color=(0.2,0.5,0.2),button='buttonJump',texture=bs.getTexture('buttonJump'),scale=1.0)

        # bs.buttonWidget(parent=self._rootWidget,label='Reset',textScale=0.7,color=(0.45,0.4,0.5),
        #                 textColor=(0.65,0.6,0.7),position=(self._width*0.5-40,20),size=(80,30),onActivateCall=self._reset)

    # def _reset(self):
    #     # simply clear our config dict and rebuild the UI
    #     getConfigDictForInputDevice(self._input,default=False,clear=True)
    #     bs.realTimer(0,self._rebuildUI)

    def _captureButton(self,pos,color,texture,button,scale=1.0):
        baseSize = 79
        b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(pos[0]-baseSize*0.5*scale,pos[1]-baseSize*0.5*scale),
                            size=(baseSize*scale,baseSize*scale),
                            texture=texture,label='',color=color)
        # make this in a timer so that it shows up on top of all other buttons
        def foo():
            uiScale = 0.66*scale*2.0
            maxWidth = 76.0*scale
            t = bs.textWidget(parent=self._rootWidget,position=(pos[0]+0.0*scale,pos[1]-(57.0-18.0)*scale),
                              color=(1,1,1,0.3),size=(0,0),hAlign='center',vAlign='top',
                              scale=uiScale, maxWidth=maxWidth,text=self._input.getButtonName(self._settings[button]));
            bs.buttonWidget(edit=b,autoSelect=True,onActivateCall=bs.Call(AwaitKeyboardInputWindow,button,t,self._settings))

        bs.realTimer(0,foo)

    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = True

    def _save(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        bs.playSound(bs.getSound('gunCocking'))

        dst = getConfigLocationForInputDevice(self._input,default=False)
        dst = dst[0][dst[1]]
        dst.clear()
        # store any values that aren't -1
        for key,val in self._settings.items():
            if val != -1: dst[key] = val
        # if we're allowed to phone home, send this config so we can generate more defaults in the future
        if bsUtils._shouldSubmitDebugInfo(): bsUtils.serverPut('controllerConfig',{'ua':bs.getEnvironment()['userAgentString'],'name':self._name,'config':dst,'v':2})
        bs.applySettings()
        bs.writeConfig()

        uiGlobals['mainMenuWindow'] = ControllersWindow(transition='inLeft').getRootWidget()
        global gCanAskToConfigGamePads
        gCanAskToConfigGamePads = True


def getConfigLocationForInputDevice(device,default):
    bsConfig = bs.getConfig()
    name = device.getName()
    if not bsConfig.has_key("Controllers"): bsConfig["Controllers"] = {}
    jsconfig = bsConfig["Controllers"]
    if not jsconfig.has_key(name): jsconfig[name] = {}
    uniqueID = device.getUniqueIdentifier()
    if default:
        if jsconfig[name].has_key(uniqueID): del(jsconfig[name][uniqueID])
        if not 'default' in jsconfig[name]: jsconfig[name]['default'] = {}
        return jsconfig[name],'default'
    else:
        if not uniqueID in jsconfig[name]: jsconfig[name][uniqueID] = {}
        return jsconfig[name],uniqueID

class EditSoundtrackWindow(Window):

    def __init__(self,existingSoundtrack,transition='inRight'):

        bsConfig = bs.getConfig()
        
        self._R = R = bs.getResource('editSoundtrackWindow')

        self._folderTex = bs.getTexture('folder')
        self._fileTex = bs.getTexture('file')

        self._width = 648
        self._height = 395 if gSmallUI else 450 if gMedUI else 560
        spacing = 40
        buttonWidth = 350
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scale=2.08 if gSmallUI else 1.5 if gMedUI else 1.0,
                                              stackOffset=(0,-48) if gSmallUI else (0,15) if gMedUI else (0,0))

        cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(38,self._height-60),size=(160,60),
                                           autoSelect=True,label=bs.getResource('cancelText'),scale=0.8)
        saveButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-168,self._height-60),
                                         autoSelect=True,size=(160,60),label=bs.getResource('saveText'),scale=0.8)
        bs.widget(edit=saveButton,leftWidget=cancelButton)
        bs.widget(edit=cancelButton,rightWidget=saveButton)
        t = bs.textWidget(parent=self._rootWidget,position=(0,self._height-50),
                          size=(self._width,25),
                          text=(R.editSoundtrackText if existingSoundtrack is not None else R.newSoundtrackText),color=gTitleColor,
                          hAlign="center",vAlign="center",maxWidth=280)
        v = self._height - 110

        # make sure config exists
        try: bsConfig['Soundtracks']
        except Exception: bsConfig['Soundtracks'] = {}

        if existingSoundtrack is not None:
            # if they passed just a name, pull info from that soundtrack
            if type(existingSoundtrack) is unicode:
                self._soundtrack = copy.deepcopy(bsConfig['Soundtracks'][existingSoundtrack])
                self._soundtrackName = existingSoundtrack
                self._existingSoundtrackName = existingSoundtrack
                self._lastEditedSongType = None
            elif type(existingSoundtrack) is str:
                print 'ERROR; got str existingSoundtrack'
            else:
                # otherwise they can pass info on an in-progress edit
                self._soundtrack = existingSoundtrack['soundtrack']
                self._soundtrackName = existingSoundtrack['name']
                self._existingSoundtrackName = existingSoundtrack['existingName']
                self._lastEditedSongType = existingSoundtrack['lastEditedSongType']
        else:
            self._soundtrackName = None
            self._existingSoundtrackName = None
            self._soundtrack = {}
            self._lastEditedSongType = None

        bs.textWidget(parent=self._rootWidget,text=R.nameText,maxWidth=80,scale=0.8,
                      position=(105,v+19),color=(0.8,0.8,0.8,0.5),size=(0,0),hAlign='right',vAlign='center')

        # if there's no initial value, find a good initial unused name
        if existingSoundtrack is None:
            i = 1
            stNameText = bs.uni(self._R.newSoundtrackNameText)
            if u'${COUNT}' not in stNameText: stNameText = stNameText+u' ${COUNT}' # make sure we insert number *somewhere*
            while True:
                self._soundtrackName = stNameText.replace(u'${COUNT}',unicode(i))
                if self._soundtrackName not in bsConfig['Soundtracks']: break
                i += 1

        self._textField = bs.textWidget(parent=self._rootWidget,position=(120,v-5),size=(self._width - 160,43),
                                        text=self._soundtrackName,hAlign="left",
                                        vAlign="center",
                                        maxChars=32,
                                        autoSelect=True,
                                        editable=True,padding=4,
                                        onReturnPressCall=self._doItWithSound)
        
        scrollHeight = self._height - 180
        self._scrollWidget = scrollWidget = bs.scrollWidget(parent=self._rootWidget,highlight=False,position=(40,v-(scrollHeight+10)),size=(self._width-80,scrollHeight),simpleCullingV=10)
        bs.widget(edit=self._textField,downWidget=self._scrollWidget)
        self._col = bs.columnWidget(parent=scrollWidget)

        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=self._col,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)

        self._songTypeButtons = {}
        self._refresh()
        bs.buttonWidget(edit=cancelButton,onActivateCall=self._cancel)
        bs.containerWidget(edit=self._rootWidget,cancelButton=cancelButton)
        bs.buttonWidget(edit=saveButton,onActivateCall=self._doIt)
        bs.containerWidget(edit=self._rootWidget,startButton=saveButton)

        bs.widget(edit=self._textField,upWidget=cancelButton)
        bs.widget(edit=cancelButton,downWidget=self._textField)
        
    def _refresh(self):
        for w in self._col.getChildren():
            w.delete()
            
        types = ['Menu',
                 'CharSelect',
                 'ToTheDeath',
                 'Onslaught',
                 'Keep Away',
                 'Race',
                 'Epic Race',
                 'ForwardMarch',
                 'FlagCatcher',
                 'Survival',
                 'Epic',
                 'Hockey',
                 'Football',
                 'Flying',
                 'Scary',
                 'Marching',
                 'GrandRomp',
                 'Chosen One',
                 'Scores',
                 'Victory',
                 ]
        typeNamesTranslated = bs.getResource('soundtrackTypeNames')
        prevTypeButton = None
        prevTestButton = None

        bColor = (0.6,0.53,0.63)
        bTextColor = (0.75,0.7,0.8)
        
        for index,songType in enumerate(types):
            r = bs.rowWidget(parent=self._col,size=(self._width-40,40))
            bs.containerWidget(edit=r,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
            try: typeName = typeNamesTranslated[songType]
            except Exception: typeName = songType
            t = bs.textWidget(parent=r,size=(230,25),alwaysHighlight=True,
                              text=typeName,scale=0.7,hAlign='left',vAlign='center',maxWidth=190)

            if songType in self._soundtrack: entry = self._soundtrack[songType]
            else: entry = None

            if entry is not None: entry = copy.deepcopy(entry) # make sure they dont muck with this after it gets to us

            iconType = self._getEntryButtonDisplayIconType(entry)
            self._songTypeButtons[songType] = b = bs.buttonWidget(parent=r,size=(230,32),label=self._getEntryButtonDisplayName(entry),
                                                                  textScale=0.6,onActivateCall=bs.Call(self._getEntry,songType,entry,typeName),
                                                                  icon=self._fileTex if iconType == 'file' else self._folderTex if iconType == 'folder' else None,
                                                                  #color=bColor,textColor=(1,1,1),
                                                                  iconColor=(1.1,0.8,0.2) if iconType == 'folder' else (1,1,1),
                                                                  leftWidget=self._textField,
                                                                  iconScale=0.7,autoSelect=True,upWidget=prevTypeButton)
                                                                  #iconScale=0.7,upWidget=prevTypeButton)
            if index == 0: bs.widget(edit=b,upWidget=self._textField)
            bs.widget(edit=b,downWidget=b)

            if self._lastEditedSongType is not None and songType == self._lastEditedSongType:
                bs.containerWidget(edit=r,selectedChild=b,visibleChild=b)
                bs.containerWidget(edit=self._col,selectedChild=r,visibleChild=r)
                bs.containerWidget(edit=self._scrollWidget,selectedChild=self._col,visibleChild=self._col)
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget,visibleChild=self._scrollWidget)
                
            if prevTypeButton is not None: bs.widget(edit=prevTypeButton,downWidget=b)
            prevTypeButton = b
            t = bs.textWidget(parent=r,size=(10,32),text='') # spacing..
            # b = bs.buttonWidget(parent=r,size=(50,32),label=self._R.testText,textScale=0.6,onActivateCall=bs.Call(self._test,songType),
            #                     color=bColor,textColor=bTextColor,autoSelect=True)
            # if index == 0: bs.widget(edit=b,upWidget=self._textField)
            b = bs.buttonWidget(parent=r,size=(50,32),label=self._R.testText,textScale=0.6,onActivateCall=bs.Call(self._test,songType),
                                upWidget=prevTestButton if prevTestButton is not None else self._textField)
            if prevTestButton is not None: bs.widget(edit=prevTestButton,downWidget=b)
            bs.widget(edit=b,downWidget=b,rightWidget=b)
            prevTestButton = b

    @classmethod
    def _restoreEditor(cls,state,musicType,entry):
        #print 'GOT CB',state,musicType,entry
        # apply the change and recreate the window
        soundtrack = state['soundtrack']
        existingEntry = None if musicType not in soundtrack else soundtrack[musicType]
        if existingEntry != entry:
            bs.playSound(bs.getSound('gunCocking'))

        # make sure this doesn't get mucked with after we get it
        if entry is not None: entry = copy.deepcopy(entry)

        entryType = bsUtils._getSoundtrackEntryType(entry)
        if entryType == 'default':
            # for 'default' entries simply exclude them from the list
            if musicType in soundtrack: del soundtrack[musicType]
        else:
            soundtrack[musicType] = entry

        uiGlobals['mainMenuWindow'] = cls(state,transition='inLeft').getRootWidget()
        
    def _getEntry(self,songType,entry,selectionTargetName):
        if selectionTargetName != '':
            selectionTargetName = "'"+selectionTargetName+"'"
        state = {'name':self._soundtrackName,'existingName':self._existingSoundtrackName,'soundtrack':self._soundtrack,'lastEditedSongType':songType}
        #bsUtils.getMusicPlayer().selectEntry(bs.Call(self._completionCB,songType),name)
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = bsUtils.getMusicPlayer().selectEntry(bs.Call(self._restoreEditor,state,songType),entry,selectionTargetName).getRootWidget()

    def _test(self,songType):
        # warn if volume is zero
        if bsInternal._getSetting("Music Volume") < 0.01:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.musicVolumeZeroWarning,color=(1,0.5,0))
        bsUtils.setMusicPlayMode('test')
        bsUtils._playMusic(songType,mode='test',testSoundtrack=self._soundtrack)

    def _getEntryButtonDisplayName(self,entry):
        entryType = bsUtils._getSoundtrackEntryType(entry)
        if entryType == 'default':
            entryName = self._R.defaultGameMusicText
        elif entryType in ('musicFile','musicFolder'):
            entryName = os.path.basename(bsUtils._getSoundtrackEntryName(entry))
        else:
            entryName = bsUtils._getSoundtrackEntryName(entry)
        return entryName

    def _getEntryButtonDisplayIconType(self,entry):
        entryType = bsUtils._getSoundtrackEntryType(entry)
        if entryType == 'musicFile':
            return 'file'
        elif entryType == 'musicFolder':
            return 'folder'
        else: return None

    # def _completionCB(self,musicType,entry):
    #     existingEntry = None if musicType not in self._soundtrack else self._soundtrack[musicType]
    #     if existingEntry != entry:
    #         bs.playSound(bs.getSound('gunCocking'))

    #     # make sure this doesn't get mucked with after we get it
    #     if entry is not None: entry = copy.deepcopy(entry)

    #     entryType = bsUtils._getSoundtrackEntryType(entry)
    #     if entryType == 'default':
    #         # for 'default' entries simply exclude them from the list
    #         if musicType in self._soundtrack: del self._soundtrack[musicType]
    #     else:
    #         self._soundtrack[musicType] = entry

    #     bs.buttonWidget(edit=self._songTypeButtons[musicType],label=self._getEntryButtonDisplayName(entry),
    #                     onActivateCall=bs.Call(self._getEntry,musicType,entry))

    def _cancel(self):
        # resets music back to normal..
        bsUtils.setMusicPlayMode('regular')

        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = SoundtracksWindow(transition='inLeft').getRootWidget()
        #self._completionCall(None)

    def _doIt(self):

        bsConfig = bs.getConfig()
        newName = bs.uni(bs.textWidget(query=self._textField))
        if newName != self._soundtrackName and newName in bsConfig['Soundtracks']:
            bs.screenMessage(self._R.cantSaveAlreadyExistsText)
            bs.playSound(bs.getSound('error'))
            return
        if len(newName) == 0:
            bs.playSound(bs.getSound('error'))
            return
        if newName == self._R.defaultSoundtrackNameText:
            bs.screenMessage(self._R.cantOverwriteDefaultText)
            bs.playSound(bs.getSound('error'))
            return

        # make sure config exists
        try: bsConfig['Soundtracks']
        except Exception: bsConfig['Soundtracks'] = {}

        # if we had an old one, delete it
        if self._existingSoundtrackName is not None and self._existingSoundtrackName in bsConfig['Soundtracks']:
            del bsConfig['Soundtracks'][self._existingSoundtrackName]
        bsConfig['Soundtracks'][newName] = self._soundtrack
        bsConfig['Soundtrack'] = newName
        
        bs.writeConfig()
        bs.playSound(bs.getSound('gunCocking'))
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        
        # resets music back to normal
        bsUtils.setMusicPlayMode('regular',forceRestart=True)

        uiGlobals['mainMenuWindow'] = SoundtracksWindow(transition='inLeft').getRootWidget()
        #self._completionCall(newName)

    def _doItWithSound(self):
        bs.playSound(bs.getSound('swish'))
        self._doIt()



class GetSoundtrackEntryTypeWindow(Window):

    def __init__(self,callback,currentEntry,selectionTargetName,transition='inRight'):

        self._R = bs.getResource('editSoundtrackWindow')

        self._callback = callback
        self._currentEntry = copy.deepcopy(currentEntry)

        self._width = 580
        self._height = 220
        spacing = 80
        
        doDefault = True
        doITunesPlaylist = bsUtils._isSoundtrackEntryTypeSupported('iTunesPlaylist')
        doMusicFile = bsUtils._isSoundtrackEntryTypeSupported('musicFile')
        doMusicFolder = bsUtils._isSoundtrackEntryTypeSupported('musicFolder')

        if doITunesPlaylist: self._height += spacing
        if doMusicFile: self._height += spacing
        if doMusicFolder: self._height += spacing

        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scale=1.7 if gSmallUI else 1.4 if gMedUI else 1.0)
        b = bs.buttonWidget(parent=self._rootWidget,position=(35,self._height-65),size=(160,60),scale=0.8,textScale=1.2,
                            label=bs.getResource('cancelText'),onActivateCall=self._onCancelPress)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-32),size=(0,0),
                          text=self._R.selectASourceText,color=gTitleColor,
                          maxWidth=230,hAlign="center",vAlign="center")

        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-56),size=(0,0),
                          text=selectionTargetName,color=gInfoTextColor,
                          scale=0.7,maxWidth=230,hAlign="center",vAlign="center")

        v = self._height - 155

        currentEntryType = bsUtils._getSoundtrackEntryType(currentEntry)

        if doDefault:
            b = defaultGameMusicButton = bs.buttonWidget(parent=self._rootWidget,size=(self._width-100,60),position=(50,v),
                                                     label=self._R.useDefaultGameMusicText,onActivateCall=self._onDefaultPress)
            if currentEntryType == 'default':
                bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            v -= spacing

        if doITunesPlaylist:
            b = iTunesPlaylistButton = bs.buttonWidget(parent=self._rootWidget,size=(self._width-100,60),position=(50,v),
                                                       label=self._R.useITunesPlaylistText,onActivateCall=self._onITunesPlaylistPress,
                                                       icon=None)
            if currentEntryType == 'iTunesPlaylist':
                bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            v -= spacing

        if doMusicFile:
            b = musicFileButton = bs.buttonWidget(parent=self._rootWidget,size=(self._width-100,60),position=(50,v),
                                                  label=self._R.useMusicFileText,onActivateCall=self._onMusicFilePress,
                                                  icon=bs.getTexture('file'))
            if currentEntryType == 'musicFile':
                bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            v -= spacing

        if doMusicFolder:
            b = musicFolderButton = bs.buttonWidget(parent=self._rootWidget,size=(self._width-100,60),position=(50,v),
                                                    label=self._R.useMusicFolderText,onActivateCall=self._onMusicFolderPress,
                                                    icon=bs.getTexture('folder'),iconColor=(1.1,0.8,0.2))
            if currentEntryType == 'musicFolder':
                bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            v -= spacing

    def _onITunesPlaylistPress(self):
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

        if bsUtils._getSoundtrackEntryType(self._currentEntry) == 'iTunesPlaylist':
            currentPlaylistEntry = bsUtils._getSoundtrackEntryName(self._currentEntry)
        else:
            currentPlaylistEntry = None
        uiGlobals['mainMenuWindow'] = GetMacITunesPlaylistWindow(self._callback,currentPlaylistEntry,self._currentEntry).getRootWidget()

    def _onMusicFilePress(self):
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        basePath = bsInternal._androidGetExternalStoragePath()
        uiGlobals['mainMenuWindow'] = FileSelectorWindow(basePath,callback=self._musicFileSelectorCB,
                                                         showBasePath=False,
                                                         validFileExtensions=bsUtils._getValidMusicFileExtensions(),
                                                         allowFolders=False).getRootWidget()

    def _onMusicFolderPress(self):
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        basePath = bsInternal._androidGetExternalStoragePath()
        uiGlobals['mainMenuWindow'] = FileSelectorWindow(basePath,callback=self._musicFolderSelectorCB,
                                                         showBasePath=False,
                                                         validFileExtensions=[],
                                                         allowFolders=True).getRootWidget()

    def _musicFileSelectorCB(self,result):
        if result is None:
            self._callback(self._currentEntry)
        else:
            self._callback({'type':'musicFile','name':bs.uni(result)})

    def _musicFolderSelectorCB(self,result):
        if result is None:
            self._callback(self._currentEntry)
        else:
            self._callback({'type':'musicFolder','name':bs.uni(result)})

    def _onDefaultPress(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        self._callback(None)
        
    def _onCancelPress(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        self._callback(self._currentEntry)

class GetMacITunesPlaylistWindow(Window):

    def __init__(self,callback,existingPlaylist,existingEntry):
        self._R = R = bs.getResource('editSoundtrackWindow')
        self._callback = callback
        self._existingPlaylist = existingPlaylist
        self._existingEntry = copy.deepcopy(existingEntry)
        self._width = 520
        self._height = 520
        self._spacing = 45
        v = self._height - 90
        v -= self._spacing*1.0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition='inRight')
        b = bs.buttonWidget(parent=self._rootWidget,position=(35,self._height-65),size=(130,50),
                            label=bs.getResource('cancelText'),onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(20,self._height-54),size=(self._width,25),
                          text=R.selectAPlaylistText,color=gTitleColor,
                          hAlign="center",vAlign="center",maxWidth=200)
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(40,v-340),size=(self._width-80,400))
        self._column = bs.columnWidget(parent=self._scrollWidget)

        # so selection loops through everything and doesn't get stuck in sub-containers
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=self._column,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        
        bs.textWidget(parent=self._column,size=(self._width-80,22),text=self._R.fetchingITunesText,color=(0.6,0.9,0.6,1.0),scale=0.8)
        bsUtils.getMusicPlayer()._thread.getPlaylists(self._playlistsCB)
        bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)

    def _playlistsCB(self,playlists):
        if self._column.exists():
            for w in self._column.getChildren():
                w.delete()
            for p in playlists:
                # if type(p) is str: pStr = p
                # else: pStr = p.encode('utf-8')
                t = bs.textWidget(parent=self._column,size=(self._width-80,30),text=p,
                                  vAlign='center',
                                  maxWidth=self._width-110,
                                  selectable=True,onActivateCall=bs.Call(self._sel,p),clickActivate=True)
                if p == self._existingPlaylist:
                    bs.columnWidget(edit=self._column,selectedChild=t,visibleChild=t)

    def _sel(self,selection):
        if self._rootWidget.exists():
            bs.containerWidget(edit=self._rootWidget,transition='outRight')
            self._callback({'type':'iTunesPlaylist','name':selection})

    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        self._callback(self._existingEntry)


class SoundtracksWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._R = R = bs.getResource('editSoundtrackWindow')
        self._width = 600
        self._height = 340 if gSmallUI else 370 if gMedUI else 440
        spacing = 40
        v = self._height - 40
        v -= spacing*1.0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=2.3 if gSmallUI else 1.6 if gMedUI else 1.0,
                                              stackOffset=(0,-18) if gSmallUI else (0,0))
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(45,self._height-60),size=(120,60),
                                                            scale=0.8,label=bs.getResource('backText'),buttonType='back',autoSelect=True)
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-35),size=(0,0),maxWidth=300,
                          text=self._R.titleText,color=gTitleColor,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=self._backButton,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(116,self._height-38))
        
        h = 43
        v = self._height - 60
        hspacing = 15
        bColor = (0.6,0.53,0.63)
        bTextColor = (0.75,0.7,0.8)

        s = 1.0 if gSmallUI else 1.13 if gMedUI else 1.4
        v -= 60.0*s
        self._newButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(100,55.0*s),
                                              onActivateCall=self._newSoundtrack,
                                              color=bColor,
                                              buttonType='square',
                                              autoSelect=True,
                                              textColor=bTextColor,
                                              textScale=0.7,
                                              label=self._R.newText)
        v -= 60.0*s


        self._editButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(100,55.0*s),
                                               onActivateCall=self._editSoundtrack,
                                               color=bColor,
                                               buttonType='square',
                                               autoSelect=True,
                                               textColor=bTextColor,
                                               textScale=0.7,
                                               label=self._R.editText)
        v -= 60.0*s

        self._duplicateButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(100,55.0*s),
                                                    onActivateCall=self._duplicateSoundtrack,
                                                    buttonType='square',
                                                    autoSelect=True,
                                                    color=bColor,
                                                    textColor=bTextColor,
                                                    textScale=0.7,
                                                    label=self._R.duplicateText)
        v -= 60.0*s

        self._deleteButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(100,55.0*s),
                                                 onActivateCall=self._deleteSoundtrack,
                                                 color=bColor,
                                                 buttonType='square',
                                                 autoSelect=True,
                                                 textColor=bTextColor,
                                                 textScale=0.7,
                                                 label=self._R.deleteText)

        v = self._height - 65
        scrollHeight = self._height - 105
        v -= scrollHeight
        hspacing = 15
        self._scrollWidget = scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(152,v),highlight=False,size=(self._width-205,scrollHeight))
        bs.widget(edit=self._scrollWidget,leftWidget=self._newButton,rightWidget=self._scrollWidget)
        self._c = bs.columnWidget(parent=scrollWidget)

        
        self._soundtracks = None
        self._selectedSoundtrack = None
        self._selectedSoundtrackIndex = None
        self._soundtrackWidgets = []
        self._allowChangingSoundtracks = False
        self._refresh()
        bs.buttonWidget(edit=backButton,onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=backButton)

        # try:
        #     for b in [self._newButton,self._editButton,self._duplicateButton,self._deleteButton]:
        #         bs.widget(edit=b,upWidget=scrollWidget)
        #     self._restoreState()
        # except Exception:
        #     bs.printException('exception wiring up SoundtracksWindow')
        
    def _doDeleteSoundtrack(self):
        try: del bs.getConfig()['Soundtracks'][self._selectedSoundtrack]
        except Exception: pass
        bs.writeConfig()
        bs.playSound(bs.getSound('shieldDown'))
        if self._selectedSoundtrackIndex >= len(self._soundtracks):
            self._selectedSoundtrackIndex = len(self._soundtracks)
        self._refresh()

    def _deleteSoundtrack(self):
        if self._selectedSoundtrack is None: return
        #if self._selectedSoundtrack == self._R.defaultSoundtrackNameText:
        if self._selectedSoundtrack == '__default__':
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.cantDeleteDefaultText)
        else:
            ConfirmWindow(self._R.deleteConfirmText.replace("${NAME}",self._selectedSoundtrack),self._doDeleteSoundtrack,450,150)

    def _duplicateSoundtrack(self):
        try: soundtracks = [bs.getConfig()['Soundtracks']]
        except Exception: bs.getConfig()['Soundtracks'] = {}

        if self._selectedSoundtrack is None: return
        if self._selectedSoundtrack == '__default__':
            pl = {}
        else:
            pl = bs.getConfig()['Soundtracks'][self._selectedSoundtrack]

        # find a valid dup name that doesn't exist
        testIndex = 1
        copyText = bs.getResource('copyOfText')
        copyWord = copyText.replace('${NAME}','').strip() # get just 'Copy' or whatnot
        baseName = self._getSoundtrackDisplayName(self._selectedSoundtrack)
        if type(baseName) is not unicode:
            print 'expected uni baseName 3fj0'
            baseName = baseName.decode('utf-8')
        
        # if it looks like a copy, strip digits and spaces off the end
        if copyWord in baseName:
            while baseName[-1].isdigit() or baseName[-1] == ' ': baseName = baseName[:-1]
        while True:
            if copyWord in baseName: testName = baseName
            else: testName = copyText.replace('${NAME}',baseName)
            if testIndex > 1: testName += ' '+str(testIndex)
            if not testName in bs.getConfig()['Soundtracks']: break
            testIndex += 1

            # testName = baseName + (copyStr if testIndex < 2 else copyStr+' '+str(testIndex))
            # if not testName in bs.getConfig()['Soundtracks']:
            #     break
            # testIndex += 1

        bs.getConfig()['Soundtracks'][testName] = copy.deepcopy(pl)
        bs.writeConfig()
        #bs.playSound(bs.getSound('gunCocking'))
        self._refresh(selectSoundtrack=testName)


    def _select(self,name,index):
        self._selectedSoundtrackIndex = index
        self._selectedSoundtrack = name

        try: currentSoundtrack = bs.getConfig()['Soundtrack']
        except Exception: currentSoundtrack = '__default__'
        #except Exception: currentSoundtrack = self._R.defaultSoundtrackNameText

        # if it varies from current, write to prefs and apply
        if currentSoundtrack != name and self._allowChangingSoundtracks:
            bs.playSound(bs.getSound('gunCocking'))
            bs.getConfig()['Soundtrack'] = self._selectedSoundtrack
            bs.writeConfig()
            # just play whats already playing.. this'll grab it from the new soundtrack
            bsUtils._playMusic(bsUtils.gMusicTypes['regular'])

    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = ConfigAudioWindow(transition='inLeft').getRootWidget()

    def _editSoundtrackWithSound(self):
        bs.playSound(bs.getSound('swish'))
        self._editSoundtrack()

    def _editSoundtrack(self):
        if self._selectedSoundtrack is None: return
        if self._selectedSoundtrack == u'__default__':
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.cantEditDefaultText)
            return

        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = EditSoundtrackWindow(existingSoundtrack=self._selectedSoundtrack).getRootWidget()

    def _getSoundtrackDisplayName(self,soundtrack):
        if soundtrack == '__default__': return self._R.defaultSoundtrackNameText
        else: return soundtrack
        
    def _refresh(self,selectSoundtrack=None):
        self._allowChangingSoundtracks = False
        oldSelection = self._selectedSoundtrack
        # if there was no prev selection, look in prefs
        if oldSelection is None:
            try: oldSelection = bs.getConfig()['Soundtrack']
            except Exception: pass
        oldSelectionIndex = self._selectedSoundtrackIndex

        # delete old
        while len(self._soundtrackWidgets) > 0: self._soundtrackWidgets.pop().delete()
        try: self._soundtracks = bs.getConfig()['Soundtracks']
        except Exception: self._soundtracks = {}
        items = self._soundtracks.items()
        items.sort(key=lambda x:x[0].lower())
        #items = [[self._R.defaultSoundtrackNameText,None]] + items # default is always first
        items = [['__default__',None]] + items # default is always first
        index = 0
        for pName,p in items:
            w = bs.textWidget(parent=self._c,size=(self._width-40,24),
                              text=self._getSoundtrackDisplayName(pName),hAlign='left',vAlign='center',
                              maxWidth=self._width-110,
                              alwaysHighlight=True,
                              onSelectCall=bs.WeakCall(self._select,pName,index),
                              onActivateCall=self._editSoundtrackWithSound,
                              selectable=True)
            if index == 0: bs.widget(edit=w,upWidget=self._backButton)
            self._soundtrackWidgets.append(w)
            # select this one if the user requested it
            if selectSoundtrack is not None:
                if pName == selectSoundtrack:
                    bs.columnWidget(edit=self._c,selectedChild=w,visibleChild=w)
            else:
                # select this one if it was previously selected
                if oldSelectionIndex is not None: # go by index if there's one
                    if index == oldSelectionIndex:
                        bs.columnWidget(edit=self._c,selectedChild=w,visibleChild=w)
                else: # otherwise look by name
                    if pName == oldSelection:
                        bs.columnWidget(edit=self._c,selectedChild=w,visibleChild=w)
            index += 1

        # explicitly run select callback on current one and re-enable callbacks
        
        # eww need to run this in a timer so it happens after our select calbacks..
        # with a small-enough time sometimes it happens before anyway.. ew.
        # need a way to just schedule a callable i guess..
        bs.realTimer(100,bs.WeakCall(self._setAllowChanging))

    def _setAllowChanging(self):
        self._allowChangingSoundtracks = True
        self._select(self._selectedSoundtrack,self._selectedSoundtrackIndex)
        
    def _newSoundtrack(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        #EditSoundtrackWindow(existingSoundtrack=None,completionCall=self._createDone)
        EditSoundtrackWindow(existingSoundtrack=None)

    def _createDone(self,newSoundtrack):
        if newSoundtrack is not None:
            bs.playSound(bs.getSound('gunCocking'))
            self._refresh(selectSoundtrack=newSoundtrack)

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._scrollWidget: selName = 'Scroll'
            elif sel == self._newButton: selName = 'New'
            elif sel == self._editButton: selName = 'Edit'
            elif sel == self._duplicateButton: selName = 'Duplicate'
            elif sel == self._deleteButton: selName = 'Delete'
            elif sel == self._backButton: selName = 'Back'
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = selName
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]
            except Exception: selName = None
            if selName == 'Scroll': sel = self._scrollWidget
            elif selName == 'New': sel = self._newButton
            elif selName == 'Edit': sel = self._editButton
            elif selName == 'Duplicate': sel = self._duplicateButton
            elif selName == 'Delete': sel = self._deleteButton
            else: sel = self._scrollWidget
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)


class AccountWindow(Window):

    def __init__(self,transition='inRight',modal=False,originWidget=None,closeOnceSignedIn=False):

        self._closeOnceSignedIn = closeOnceSignedIn
            
        bsInternal._setAnalyticsScreen('Account Window')
        
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._R = R = bs.getResource('accountSettingsWindow')
        self._modal = modal
        self._needsRefresh = False
        self._signedIn = (bsInternal._getAccountState() == 'SIGNED_IN')
        self._accountStateNum = bsInternal._getAccountStateNum()
        self._showLinked = True if self._signedIn and bsInternal._getAccountMiscReadVal('allowAccountLinking2',False) else False
        self._checkSignInTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        
        # currently we can only reset achievements on game-center..
        if self._signedIn: accountType = bsInternal._getAccountType()
        else: accountType = None
        if accountType == 'Game Center': self._canResetAchievements = True
        else: self._canResetAchievements = False
        
        env = bs.getEnvironment()
        
        self._width = 660
        self._height = 390 if gSmallUI else 430 if gMedUI else 490

        self._signInButton = None
        self._signInText = None
        
        self._scrollWidth = self._width - 100
        self._scrollHeight = self._height - 120
        self._subWidth = self._scrollWidth-20

        # determine which sign-in/sign-out buttons we should show..
        self._showSignInButtons = []

        #print 'PLATFORM',env['platform'],'SUB',env['subplatform']
        
        if env['platform'] == 'android' and env['subplatform'] == 'google':
            self._showSignInButtons.append('Google Play')
            
        elif env['platform'] == 'android' and env['subplatform'] == 'amazon':
            self._showSignInButtons.append('Game Circle')

        # elif env['platform'] == 'android' and env['subplatform'] == 'alibaba':
        #     self._showSignInButtons.append('Ali')

        # Local accounts are generally always available with a few key exceptions
        # if not (env['platform'] == 'android' and env['subplatform'] == 'alibaba'):
        self._showSignInButtons.append('Local')
        
        # show old test-account option *only* if we've been installed since before build 14101
        # (after then, people should just use device accounts for the same purpose)
        if env['testBuild'] or (env['platform'] == 'android' and env['subplatform'] in ['oculus','cardboard']):
            if bs.getConfig().get('lc14c',0) > 1:
                self._showSignInButtons.append('Test')
        
        topExtra = 15 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=2.09 if gSmallUI else 1.4 if gMedUI else 1.0,
                                              stackOffset=(0,-19) if gSmallUI else (0,0))
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(51,self._height-62),size=(120,60),scale=0.8,textScale=1.2,
                                               autoSelect=True,label=bs.getResource('doneText' if self._modal else 'backText'),
                                               buttonType='regular' if self._modal else 'back',
                                               onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-38),size=(0,0),
                          text=R.titleText,color=gTitleColor,maxWidth=self._width-340,
                          hAlign="center",vAlign="center")

        if not self._modal and gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,56),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(113,self._height-40))

            
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,
                                             highlight=False,position=((self._width-self._scrollWidth)*0.5,self._height - 65-self._scrollHeight),
                                             size=(self._scrollWidth,self._scrollHeight))
        self._subContainer = None
        self._refresh()
        self._restoreState()

    def _update(self):

        # if they want us to close once we're signed in, do so.
        if self._closeOnceSignedIn and self._signedIn:
            self._back()
            return
        
        dirty = False

        # hmm should update this to use getAccountStateNum;
        # theoretically if we switch from one signed-in account to another
        # in the background this would break.
        
        accountStateNum = bsInternal._getAccountStateNum()
        accountState = bsInternal._getAccountState()

        showLinked = True if self._signedIn and bsInternal._getAccountMiscReadVal('allowAccountLinking2',False) else False

        if accountStateNum != self._accountStateNum or self._showLinked != showLinked or self._needsRefresh:
            self._showLinked = showLinked
            accountType = bsInternal._getAccountType() if accountState == 'SIGNED_IN' else 'unknown'
            self._accountStateNum = accountStateNum
            #self._signedIn = (accountState == 'SIGNED_IN' and accountType != 'Local')
            self._signedIn = (accountState == 'SIGNED_IN')
            self._refresh()
        
        # if we've gone from signed in to signed out or vice versa we need to do a full refresh
        # if signedIn != self._signedIn:
        #     self._signedIn = signedIn
        #     self._refresh()

        # alternate our sign-in text between 'sign in' and 'signing in..' based on state..
        # if accountState == 'SIGNING_IN':
        #     if self._signInText is not None: bs.textWidget(edit=self._signInText,text=self._R.signingInText)
        #     elif self._signInButton is not None: bs.buttonWidget(edit=self._signInButton,label=self._R.signingInText)
        # elif accountState == 'SIGNED_OUT':
        #     if self._signInText is not None: bs.textWidget(edit=self._signInText,text=self._getSignInText())
        #     elif self._signInButton is not None: bs.buttonWidget(edit=self._signInButton,label=self._getSignInText())

        # go ahead and refresh some individual things that may change under us..
        self._refreshLinkedAccountsText()
        self._refreshCampaignProgressText()
        self._refreshAchievements()
        self._refreshTicketsText()
        self._refreshAccountNameText()

    def _getSignInText(self):
        t = self._R.signInText
        # env = bs.getEnvironment()
        # if (env['platform'] == 'android' and env['subplatform'] in ['amazon']):
        #     t = bs.getSpecialChar('gameCircleLogo')+' '+t
        return t
            
    def _refresh(self):

        import bsCoopGame

        env = bs.getEnvironment()
        #isGoogle = True if (env['platform'] == 'android' and env['subplatform'] in ['google']) else False

        accountState = bsInternal._getAccountState()
        accountType = bsInternal._getAccountType() if accountState == 'SIGNED_IN' else 'unknown'

        isGoogle = True if accountType == 'Google Play' else False
        
        # showLocalSignedInAs = True if accountType == 'Local' else False
        showLocalSignedInAs = False
        localSignedInAsSpace = 50
        
        showSignedInAs = True if self._signedIn else False
        signedInAsSpace = 95
        
        showSignInBenefits = True if not self._signedIn else False
        signInBenefitsSpace = 80

        showSigningInText = True if accountState == 'SIGNING_IN' else False
        signingInTextSpace = 80

        showGooglePlaySignInButton = True if (accountState == 'SIGNED_OUT' and 'Google Play' in self._showSignInButtons) else False
        showGameCircleSignInButton = True if (accountState == 'SIGNED_OUT' and 'Game Circle' in self._showSignInButtons) else False
        showAliSignInButton = True if (accountState == 'SIGNED_OUT' and 'Ali' in self._showSignInButtons) else False
        showTestSignInButton = True if (accountState == 'SIGNED_OUT' and 'Test' in self._showSignInButtons) else False
        showDeviceSignInButton = True if (accountState == 'SIGNED_OUT' and 'Local' in self._showSignInButtons) else False
        signInButtonSpace = 70
        
        showGameServiceButton = True if (self._signedIn and accountType in ['Game Center','Game Circle']) else False
        gameServiceButtonSpace = 60

        showLinkedAccountsText = True if self._signedIn and bsInternal._getAccountMiscReadVal('allowAccountLinking2',False) else False
        linkedAccountsTextSpace = 40

        showAchievementsButton = True if (self._signedIn and accountType in ('Google Play','Alibaba','Local','OUYA','Test')) else False
        achievementsButtonSpace = 60
        
        showAchievementsText = True if (self._signedIn and not showAchievementsButton) else False
        achievementsTextSpace = 27

        showLeaderboardsButton = True if (self._signedIn and isGoogle) else False
        leaderboardsButtonSpace = 60
        
        showCampaignProgress = True if self._signedIn else False
        campaignProgressSpace = 27

        showTickets = True if self._signedIn else False
        ticketsSpace = 27
        
        #showResetProgressButton = True if self._signedIn else False
        showResetProgressButton = False
        resetProgressButtonSpace = 70

        showPlayerProfilesButton = True if self._signedIn else False
        playerProfilesButtonSpace = 70
        
        showLinkAccountsButton = True if self._signedIn and bsInternal._getAccountMiscReadVal('allowAccountLinking2',False) else False
        linkAccountsButtonSpace = 70
        
        #showSignOutButton = True if (self._signedIn and self._showSignOutButton) else False
        showSignOutButton = True if (self._signedIn and accountType in ['Test','Local','Google Play']) else False
        signOutButtonSpace = 70
        
        if self._subContainer is not None: self._subContainer.delete()

        self._subHeight = 60

        if showLocalSignedInAs: self._subHeight += localSignedInAsSpace
        if showSignedInAs: self._subHeight += signedInAsSpace
        if showSigningInText: self._subHeight += signingInTextSpace
        if showGooglePlaySignInButton: self._subHeight += signInButtonSpace
        if showGameCircleSignInButton: self._subHeight += signInButtonSpace
        if showAliSignInButton: self._subHeight += signInButtonSpace
        if showTestSignInButton: self._subHeight += signInButtonSpace
        if showDeviceSignInButton: self._subHeight += signInButtonSpace
        if showGameServiceButton: self._subHeight += gameServiceButtonSpace
        if showLinkedAccountsText: self._subHeight += linkedAccountsTextSpace
        if showAchievementsText: self._subHeight += achievementsTextSpace
        if showAchievementsButton: self._subHeight += achievementsButtonSpace
        if showLeaderboardsButton: self._subHeight += leaderboardsButtonSpace
        if showCampaignProgress: self._subHeight += campaignProgressSpace
        if showTickets: self._subHeight += ticketsSpace
        if showSignInBenefits: self._subHeight += signInBenefitsSpace
        if showResetProgressButton: self._subHeight += resetProgressButtonSpace
        if showPlayerProfilesButton: self._subHeight += playerProfilesButtonSpace
        if showLinkAccountsButton: self._subHeight += linkAccountsButtonSpace
        if showSignOutButton: self._subHeight += signOutButtonSpace
        
        # if (self._signedIn and self._showSignOutButton) or (not self._signedIn and self._showSignInButton):
        #     self._subHeight += 50
        
        self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,
                                                    size=(self._subWidth,self._subHeight),background=False)
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=self._subContainer,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)

        firstSelectable = None

        v = self._subHeight - 10

        if showLocalSignedInAs:
            v -= localSignedInAsSpace * 0.6
            t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                              text=bs.getResource('accountSettingsWindow.deviceSpecificAccountText').replace(u'${NAME}',bsInternal._getAccountDisplayString()),scale=0.7,
                              color=(0.5,0.5,0.6),maxWidth=self._subWidth*0.9,
                              flatness=1.0,
                              hAlign="center",vAlign="center")
            v -= localSignedInAsSpace * 0.4
            
        if showSignedInAs:
            v -= signedInAsSpace*0.2

            txt = bs.getResource('accountSettingsWindow.youAreSignedInAsText',fallback='accountSettingsWindow.youAreLoggedInAsText')
            t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                              text=txt,scale=0.9,color=gTitleColor,maxWidth=self._subWidth*0.9,
                              hAlign="center",vAlign="center")

            v -= signedInAsSpace*0.4
            #v -= 41

            # if self._signedIn:
            self._accountNameText = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                                                  scale=1.5,maxWidth=self._subWidth*0.9,resScale=1.5,
                                                  color=(1,1,1,1),
                                                  hAlign="center",vAlign="center")
            self._refreshAccountNameText()
            # else:
            #     self._accountNameText = None
            #     txt = bs.getResource('accountSettingsWindow.notSignedInText',fallback='accountSettingsWindow.notLoggedInText')
            #     t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
            #                       scale=1.3,maxWidth=self._subWidth*0.9,
            #                       text=txt,color=(0.6,0.6,0.6,1),
            #                       hAlign="center",vAlign="center")
            v -= signedInAsSpace*0.4
        else: self._accountNameText = None

        # accountButtonIcon = None
        # accountButtonIconColor=(1,1,1)
        # accountButtonTextColor=(0.75,1.0,0.7)
        # if (env['platform'] == 'android' and env['subplatform'] in ['amazon']):
        #     accountButtonIcon = bs.getTexture('gameCircleIcon')
        # elif (env['platform'] == 'android' and env['subplatform'] in ['google']):
        #     accountButtonIcon = bs.getTexture('googlePlayGamesIcon')
        #     accountButtonIconColor=(0,1,0)
        #     accountButtonTextColor=(0,1,0)
        # elif env['testBuild']:
        #     accountButtonIcon = bs.getTexture('logo')
            
        # if (self._signedIn and self._showSignOutButton) or (not self._signedIn and self._showSignInButton):

        if showSignInBenefits:
            v -= signInBenefitsSpace
            env = bs.getEnvironment()
            if env['platform'] in ['mac','ios'] and env['subplatform'] == 'appstore':
                extra = '\n'+bs.getResource('signInWithGameCenterText')
            else: extra = ''
            
            t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v+signInBenefitsSpace*0.4),size=(0,0),
                              text=self._R.signInInfoText+extra,maxHeight=signInBenefitsSpace*0.9,
                              scale=0.9,color=gInfoTextColor,maxWidth=self._subWidth*0.8,
                              hAlign="center",vAlign="center")

        if showSigningInText:
            v -= signingInTextSpace

            t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v+signingInTextSpace*0.5),size=(0,0),
                              text=bs.getResource('accountSettingsWindow.signingInText'),
                              scale=0.9,
                              color=(0,1,0),
                              maxWidth=self._subWidth*0.8,
                              hAlign="center",vAlign="center")

        if showGooglePlaySignInButton:
            buttonWidth = 350
            v -= signInButtonSpace
            self._signInGooglePlayButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v-20),
                                                               autoSelect=True,size=(buttonWidth,60),
                                                               label=bs.getSpecialChar('googlePlusLogo')+self._R.signInWithGooglePlayText,
                                                               onActivateCall=lambda: self._signInPress('Google Play'))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            bs.widget(edit=b,showBufferBottom=40,showBufferTop=100)
            self._signInText = None

        if showGameCircleSignInButton:
            buttonWidth = 350
            v -= signInButtonSpace
            self._signInGameCircleButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v-20),
                                                               autoSelect=True,size=(buttonWidth,60),
                                                               label=bs.getSpecialChar('gameCircleLogo')+self._R.signInWithGameCircleText,
                                                               onActivateCall=lambda: self._signInPress('Game Circle'))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            bs.widget(edit=b,showBufferBottom=40,showBufferTop=100)
            self._signInText = None

        if showAliSignInButton:
            buttonWidth = 350
            v -= signInButtonSpace
            self._signInAliButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v-20),
                                                        autoSelect=True,size=(buttonWidth,60),
                                                        label=bs.getSpecialChar('alibabaLogo')+self._R.signInText,
                                                        onActivateCall=lambda: self._signInPress('Ali'))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            bs.widget(edit=b,showBufferBottom=40,showBufferTop=100)
            self._signInText = None
            
            
        if showDeviceSignInButton:
            buttonWidth = 350
            v -= signInButtonSpace
            self._signInDeviceButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v-20),
                                                           autoSelect=True,size=(buttonWidth,60),
                                                           label='',
                                                           onActivateCall=lambda: self._signInPress('Local'))
            bs.textWidget(parent=self._subContainer,drawController=b,hAlign='center',vAlign='center',size=(0,0),position=(self._subWidth*0.5,v+17),
                          text=bs.getSpecialChar('localAccount')+self._R.signInWithDeviceText,
                          maxWidth=buttonWidth*0.8,color=(0.75,1.0,0.7))
            bs.textWidget(parent=self._subContainer,drawController=b,hAlign='center',vAlign='center',size=(0,0),position=(self._subWidth*0.5,v-4),
                          text=self._R.signInWithDeviceInfoText,flatness=1.0,
                          scale=0.57,maxWidth=buttonWidth*0.9,color=(0.55,0.8,0.5))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            bs.widget(edit=b,showBufferBottom=40,showBufferTop=100)
            self._signInText = None
            
        # old test-account option.. 
        if showTestSignInButton:
            buttonWidth = 350
            v -= signInButtonSpace
            self._signInTestButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v-20),
                                                         autoSelect=True,size=(buttonWidth,60),
                                                         label='',
                                                         onActivateCall=lambda: self._signInPress('Test'))
            bs.textWidget(parent=self._subContainer,drawController=b,hAlign='center',vAlign='center',size=(0,0),position=(self._subWidth*0.5,v+17),
                          text=bs.getSpecialChar('testAccount')+self._R.signInWithTestAccountText,
                          maxWidth=buttonWidth*0.8,color=(0.75,1.0,0.7))
            bs.textWidget(parent=self._subContainer,drawController=b,hAlign='center',vAlign='center',size=(0,0),position=(self._subWidth*0.5,v-4),
                          text=self._R.signInWithTestAccountInfoText,flatness=1.0,
                          scale=0.57,maxWidth=buttonWidth*0.9,color=(0.55,0.8,0.5))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            bs.widget(edit=b,showBufferBottom=40,showBufferTop=100)
            self._signInText = None


        # the button to go to OS-Specific leaderboards/high-score-lists/etc.
        if showGameServiceButton:
            buttonWidth = 300
            v -= gameServiceButtonSpace*0.85
            accountType = bsInternal._getAccountType()
            if accountType == 'Game Center':
                #accountTypeIcon = bs.getTexture('gameCenterIcon')
                accountTypeName = bs.getResource('gameCenterText')
            elif accountType == 'Game Circle':
                #accountTypeIcon = bs.getTexture('gameCircleIcon')
                accountTypeName = bs.getResource('gameCircleText')
            else: raise Exception("unknown account type: '"+str(accountType)+"'")
            self._gameServiceButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                           color=(0.55,0.5,0.6),textColor=gInfoTextColor,autoSelect=True,
                                                           #icon = accountTypeIcon,
                                                           onActivateCall=bsInternal._showOnlineScoreUI,
                                                           size=(buttonWidth,50),label=accountTypeName)
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            v -= gameServiceButtonSpace*0.15
        else:
            self.gameServiceButton = None

        if showLinkedAccountsText:
            v -= linkedAccountsTextSpace*0.5
            self._linkedAccountsText = t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                                                         scale=0.9,color=gInfoTextColor,maxWidth=self._subWidth*0.95,
                                                         hAlign="center",vAlign="center")
            v -= linkedAccountsTextSpace*0.5
            self._refreshLinkedAccountsText()
        else:
            self._linkedAccountsText = None

        if showAchievementsText:
            v -= achievementsTextSpace*0.5
            self._achievementsText = t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                              scale=0.9,color=gInfoTextColor,maxWidth=self._subWidth*0.8,
                              hAlign="center",vAlign="center")
            v -= achievementsTextSpace*0.5
        else:
            self._achievementsText = None

        if showAchievementsButton:
            buttonWidth = 300
            v -= achievementsButtonSpace*0.85
            self._achievementsButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                           color=(0.55,0.5,0.6),textColor=gInfoTextColor,autoSelect=True,
                                                           icon = bs.getTexture('googlePlayAchievementsIcon' if isGoogle else 'achievementsIcon'),
                                                           iconColor=(0.8,0.95,0.7) if isGoogle else (1,1,1),
                                                           onActivateCall=self._onAchievementsPress,
                                                           size=(buttonWidth,50),label='')
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            v -= achievementsButtonSpace*0.15
        else:
            self._achievementsButton = None

        if showAchievementsText or showAchievementsButton: self._refreshAchievements()
            
        if showLeaderboardsButton:
            buttonWidth = 300
            v -= leaderboardsButtonSpace*0.85
            self._leaderboardsButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                           color=(0.55,0.5,0.6),textColor=gInfoTextColor,autoSelect=True,
                                                           icon = bs.getTexture('googlePlayLeaderboardsIcon'),
                                                           iconColor=(0.8,0.95,0.7),
                                                           onActivateCall=self._onLeaderboardsPress,
                                                           size=(buttonWidth,50),label=bs.getResource('leaderboardsText'))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)
            v -= leaderboardsButtonSpace*0.15
        else:
            self._leaderboardsButton = None

        if showCampaignProgress:
            v -= campaignProgressSpace*0.5
            
            self._campaignProgressText = t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                                                           scale=0.9,color=gInfoTextColor,maxWidth=self._subWidth*0.8,
                                                           hAlign="center",vAlign="center")
            v -= campaignProgressSpace*0.5
            self._refreshCampaignProgressText()
        else:
            self._campaignProgressText = None


        if showTickets:
            v -= ticketsSpace*0.5
            
            self._ticketsText = t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v),size=(0,0),
                                                  scale=0.9,color=gInfoTextColor,maxWidth=self._subWidth*0.8,flatness=1.0,
                                                  hAlign="center",vAlign="center")
            v -= ticketsSpace*0.5
            self._refreshTicketsText()
            

        else:
            self._ticketsText = None


        # bit of spacing before the reset/sign-out section
        v -= 5
        
        buttonWidth = 250
        if showResetProgressButton:
            confirmText = self._R.resetProgressConfirmText if self._canResetAchievements else self._R.resetProgressConfirmNoAchievementsText
            v -= resetProgressButtonSpace
            self._resetProgressButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                            color=(0.55,0.5,0.6),textColor=(0.75,0.7,0.8),autoSelect=True,
                                                            size=(buttonWidth,60),label=self._R.resetProgressText,
                                                            onActivateCall=bs.Call(ConfirmWindow,text=confirmText,
                                                                         width=500,height=200,action=self._resetProgress))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton)

            
        if showPlayerProfilesButton:
            v -= playerProfilesButtonSpace
            self._playerProfilesButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                             autoSelect=True,size=(buttonWidth,60),
                                                             label=bs.getResource('playerProfilesWindow.titleText'),
                                                             color=(0.55,0.5,0.6),
                                                             icon=bs.getTexture('cuteSpaz'),
                                                             textColor=(0.75,0.7,0.8),
                                                             onActivateCall=self._playerProfilesPress)
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton,showBufferBottom=0)

        if showLinkAccountsButton:
            v -= linkAccountsButtonSpace
            self._linkAccountsButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                           autoSelect=True,size=(buttonWidth,60),
                                                           label='',color=(0.55,0.5,0.6),
                                                           onActivateCall=self._linkAccountsPress)
            bs.textWidget(parent=self._subContainer,drawController=b,hAlign='center',vAlign='center',size=(0,0),
                          position=(self._subWidth*0.5,v+17+20),
                          text=self._R.linkAccountsText,
                          maxWidth=buttonWidth*0.8,color=(0.75,0.7,0.8))
            bs.textWidget(parent=self._subContainer,drawController=b,hAlign='center',
                          vAlign='center',size=(0,0),position=(self._subWidth*0.5,v-4+20),
                          text=self._R.linkAccountsInfoText,flatness=1.0,
                          scale=0.5,maxWidth=buttonWidth*0.8,color=(0.75,0.7,0.8))
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton,showBufferBottom=50)
            
        if showSignOutButton:
            v -= signOutButtonSpace
            self._signOutButton = b = bs.buttonWidget(parent=self._subContainer,position=((self._subWidth-buttonWidth)*0.5,v),
                                                      size=(buttonWidth,60),label=self._R.signOutText,
                                                      color=(0.55,0.5,0.6),textColor=(0.75,0.7,0.8),
                                                      #icon=accountButtonIcon,
                                                      autoSelect=True,
                                                      onActivateCall=self._signOutPress)
            if firstSelectable is None: firstSelectable = b
            bs.widget(edit=b,leftWidget=self._backButton,showBufferBottom=15)

        # whatever the topmost selectable thing is, we want it to scroll all the way up when we select it
        if firstSelectable is not None:
            bs.widget(edit=firstSelectable,upWidget=self._backButton,showBufferTop=400)
            # (this should re-scroll us to the top..)
            bs.containerWidget(edit=self._subContainer,visibleChild=firstSelectable)

        self._needsRefresh = False
        
    def _onAchievementsPress(self):
        accountState = bsInternal._getAccountState()
        accountType = bsInternal._getAccountType() if accountState == 'SIGNED_IN' else 'unknown'
        # for google play we use the built-in UI; otherwise pop up our own
        if accountType == 'Google Play':
            bs.realTimer(150,bs.Call(bsInternal._showOnlineScoreUI,'achievements')),
        elif accountType != 'unknown':
            AchievementsWindow(position=self._achievementsButton.getScreenSpaceCenter())
        else:
            print 'ERROR: unknown account type in onAchievementsPress'
            

    def _onLeaderboardsPress(self):
        bs.realTimer(150,bs.Call(bsInternal._showOnlineScoreUI,'leaderboards')),

    def _refreshLinkedAccountsText(self):
        if self._linkedAccountsText is None: return
        ourAccount = bsInternal._getAccountDisplayString()
        accounts = bsInternal._getAccountMiscReadVal2('linkedAccounts',[])
        accounts = [a for a in accounts if a != ourAccount]
        accountsStr = u', '.join(accounts) if accounts else bs.translate('settingNames','None')
        bs.textWidget(edit=self._linkedAccountsText,text=bs.uni(self._R.linkedAccountsText)+' '+accountsStr)

    def _refreshCampaignProgressText(self):
        if self._campaignProgressText is None: return
        try:
            campaign = bsCoopGame.getCampaign('Default')
            levels = campaign.getLevels()
            levelsComplete = sum((1 if l.getComplete() else 0) for l in levels)
            # last level cant be completed; hence the -1
            progress = min(1.0,float(levelsComplete)/(len(levels)-1))
            pStr = self._R.campaignProgressText.replace('${PROGRESS}',str(int(progress*100.0))+'%')
        except Exception:
            pStr = '?'
            bs.printException('error calculating co-op campaign progress')
        bs.textWidget(edit=self._campaignProgressText,text=pStr)
                
    def _refreshTicketsText(self):
        if self._ticketsText is None: return
        try: tcStr = str(bsInternal._getAccountTicketCount())
        except Exception:
            bs.printException()
            tcStr = '-'
        bs.textWidget(edit=self._ticketsText,
                      text=self._R.ticketsText.replace('${COUNT}',tcStr))

    def _refreshAccountNameText(self):
        if self._accountNameText is None: return
        try: nameStr = bsInternal._getAccountDisplayString()
        except Exception:
            bs.printException()
            nameStr = u'??'
        bs.textWidget(edit=self._accountNameText,text=nameStr)
        
    def _refreshAchievements(self):
        import bsAchievement
        if self._achievementsText is None and self._achievementsButton is None: return
        complete = sum(1 if a.isComplete() else 0 for a in bsAchievement.gAchievements)
        total = len(bsAchievement.gAchievements)
        txtFinal = self._R.achievementProgressText.replace('${COUNT}',str(complete)).replace('${TOTAL}',str(total))

        if self._achievementsText is not None: bs.textWidget(edit=self._achievementsText,text=txtFinal)
        if self._achievementsButton is not None: bs.buttonWidget(edit=self._achievementsButton,label=txtFinal)

    def _linkAccountsPress(self):
        import bsUI2
        bsUI2.LinkAccountsWindow(originWidget=self._linkAccountsButton)

    def _playerProfilesPress(self):
        # bsUI2.LinkAccountsWindow(originWidget=self._linkAccountsButton)
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition="outLeft")
        PlayerProfilesWindow(originWidget=self._playerProfilesButton)
        
    def _signOutPress(self):
        bsInternal._signOut()

        bsConfig = bs.getConfig()
        
        # take note that its our explit intention to not be signed in at this point...
        bsConfig['Auto Account State'] = 'SIGNED_OUT'

        # clear this old key if it exists too...
        if bsInternal._isUsingInternalAccounts():
            if 'Test Account Sign In' in bsConfig:
                del bsConfig['Test Account Sign In']
            
        bs.writeConfig()
        
        bs.buttonWidget(edit=self._signOutButton,label=self._R.signingOutText)

    def _signInPress(self,accountType,showTestWarning=True):
        internalAccounts = bsInternal._isUsingInternalAccounts()
        bsInternal._signIn(accountType)
        # make note of the type account we're *wanting* to be signed in with..
        bs.getConfig()['Auto Account State'] = accountType
        bs.writeConfig()
        self._needsRefresh = True
        bs.realTimer(100,bs.WeakCall(self._update))
        
    def _resetProgress(self):
        try:
            import bsCoopGame
            # FIXME - this would need to happen server-side these days
            if self._canResetAchievements:
                bs.getConfig()['Achievements'] = {}
                bsInternal._resetAchievements()
            campaign = bsCoopGame.getCampaign('Default')
            campaign.reset() # also writes the config..
            campaign = bsCoopGame.getCampaign('Challenges')
            campaign.reset() # also writes the config..
        except Exception:
            bs.printException('exception resetting co-op campaign progress')

        bs.playSound(bs.getSound('shieldDown'))
        self._refresh()
        
    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)

        if not self._modal:
            uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._backButton: selName = 'Back'
            elif sel == self._scrollWidget: selName = 'Scroll'
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = selName
        except Exception:
            bs.printException('exception saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]
            except Exception: selName = None
            if selName == 'Back': sel = self._backButton
            elif selName == 'Scroll': sel = self._scrollWidget
            else: sel = self._backButton
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)


class ConfigAudioWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._R = R = bs.getResource('audioSettingsWindow')

        spacing = 50
        width = 460
        height = 210

        showVRHeadRelativeAudio = True if bs.getEnvironment()['vrMode'] else False

        if showVRHeadRelativeAudio: height += 70
        
        showSoundtracks = False
        if bsUtils.haveMusicPlayer():
            showSoundtracks = True
            height += spacing*2.0

        baseScale=2.05 if gSmallUI else 1.6 if gMedUI else 1.0
        popupMenuScale = baseScale*1.2

        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,scale=baseScale,
                                              scaleOriginStackOffset=scaleOrigin,
                                              stackOffset=(0,-20) if gSmallUI else (0,0))
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(35,height-55),size=(120,60),scale=0.8,textScale=1.2,
                                                            label=bs.getResource('backText'),buttonType='back',onActivateCall=self._back,autoSelect=True)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        v = height - 60
        v -= spacing*1.0
        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-32),size=(0,0),
                          text=R.titleText,color=gTitleColor,
                          maxWidth=180,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=self._backButton,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(98,height-32))
        

        self._soundVolumeWidgets = sv = configTextBox(parent=self._rootWidget,position=(40,v),xOffset=10,name="Sound Volume",displayName=R.soundVolumeText,type="float",minVal=0,maxVal=1.0,increment=0.1)
        v -= spacing
        self._musicVolumeWidgets = mv = configTextBox(parent=self._rootWidget,position=(40,v),xOffset=10,name="Music Volume",displayName=R.musicVolumeText,type="float",minVal=0,maxVal=1.0,increment=0.1,callback=bsUtils._musicVolumeChanged,changeSound=None)

        v -= 0.5*spacing
        
        if showVRHeadRelativeAudio:
            v -= 40
            t = bs.textWidget(parent=self._rootWidget,position=(40,v+24),size=(0,0),
                              text=self._R.headRelativeVRAudioText,
                              color=(0.8,0.8,0.8),maxWidth=230,
                              hAlign="left",vAlign="center")
            
            p = PopupMenu(parent=self._rootWidget,position=(290,v),width=120,buttonSize=(135,50),scale=popupMenuScale,
                          choices=['Auto','On','Off'],
                          choicesDisplay=[bs.getResource('autoText'),bs.getResource('onText'),bs.getResource('offText')],
                          currentChoice=bsInternal._getSetting('VR Head Relative Audio'),onValueChangeCall=self._setVRHeadRelativeAudio)
            self._vrHeadRelativeAudioButton = p.getButtonWidget()
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,v-11),size=(0,0),
                              text=self._R.headRelativeVRAudioInfoText,scale=0.5,
                              color=(0.7,0.8,0.7),maxWidth=400,flatness=1.0,
                              hAlign="center",vAlign="center")
            v -= 30
        else:
            self._vrHeadRelativeAudioButton = None
            

        
        if showSoundtracks:
            v -= 1.2*spacing
            self._soundtrackButton = b = bs.buttonWidget(parent=self._rootWidget,position=((width-310)/2,v),size=(310,50),autoSelect=True,
                                                   label=R.soundtrackButtonText,onActivateCall=self._doSoundtracks)
            v -= spacing*0.5
            bs.textWidget(parent=self._rootWidget,position=(0,v),size=(width,20),text=R.soundtrackDescriptionText,
                          flatness=1.0,hAlign='center',scale=0.5,color=(0.7,0.8,0.7,1.0),maxWidth=400)
        else:
            self._soundtrackButton = None

        # tweak a few navigation bits
        try:
            bs.widget(edit=backButton,downWidget=sv['minusButton'])
            # if self._soundtrackButton is not None:
            #     bs.widget(edit=self._soundtrackButton,upWidget=mv['minusButton'])
        except Exception:
            bs.printException('error wiring ConfigAudioWindow')

        self._restoreState()

    def _setVRHeadRelativeAudio(self,val):
        bs.getConfig()['VR Head Relative Audio'] = val
        bs.applySettings()
        bs.writeConfig()
            
    def _doSoundtracks(self):
        # we require disk access for soundtracks;
        # if we don't have it, request it..
        if not bsInternal._havePermission("storage"):
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('storagePermissionAccessText'),color=(1,0,0))
            bsInternal._requestPermission("storage")
            return
        
        # currently cant do this if we're in a non-host-session
        # if bsInternal._getForegroundHostSession() is None:
        #     bs.screenMessage(bs.getResource('editSoundtrackWindow.cantEditWhileConnectedOrInReplayText'),color=(1,0,0))
        #     bs.playSound(bs.getSound('error'))
        #     return
        
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = SoundtracksWindow(originWidget=self._soundtrackButton).getRootWidget()

    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = SettingsWindow(transition='inLeft').getRootWidget()

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._soundVolumeWidgets['minusButton']: selName = 'SoundMinus'
            elif sel == self._soundVolumeWidgets['plusButton']: selName = 'SoundPlus'
            elif sel == self._musicVolumeWidgets['minusButton']: selName = 'MusicMinus'
            elif sel == self._musicVolumeWidgets['plusButton']: selName = 'MusicPlus'
            elif sel == self._soundtrackButton: selName = 'Soundtrack'
            elif sel == self._backButton: selName = 'Back'
            elif sel == self._vrHeadRelativeAudioButton: selName = 'VRHeadRelative'
            else: raise Exception("unrecognized selected widget")
            gWindowStates[self.__class__.__name__] = selName
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]
            except Exception: selName = None
            if selName == 'SoundMinus': sel = self._soundVolumeWidgets['minusButton']
            elif selName == 'SoundPlus': sel = self._soundVolumeWidgets['plusButton']
            elif selName == 'MusicMinus': sel = self._musicVolumeWidgets['minusButton']
            elif selName == 'MusicPlus': sel = self._musicVolumeWidgets['plusButton']
            elif selName == 'VRHeadRelative': sel = self._vrHeadRelativeAudioButton
            elif selName == 'Soundtrack': sel = self._soundtrackButton
            elif selName == 'Back': sel = self._backButton
            else: sel = self._backButton
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)


class GraphicsWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._R = R = bs.getResource('graphicsSettingsWindow')
        env = bs.getEnvironment()
        
        spacing = 32
        self._haveSelectedChild = False
        ua = env['userAgentString']
        interfaceType = env['interfaceType']
        width = 450
        height = 302

        self._showFullscreen = False
        fullscreenSpacingTop = spacing*0.2
        fullscreenSpacing = spacing*1.2
        if interfaceType == 'desktop':
            self._showFullscreen = True
            height += fullscreenSpacing+fullscreenSpacingTop

        showGamma = False
        gammaSpacing = spacing*1.3
        #if interfaceType == 'desktop':
        if bsInternal._hasGammaControl():
            showGamma = True
            height += gammaSpacing

        showVSync = False
        if 'Mac' in ua or 'macos' in ua:
            showVSync = True

        showResolution = True
        if env['vrMode']: showResolution = False
            
        baseScale = 2.4 if gSmallUI else 1.5 if gMedUI else 1.0
        popupMenuScale = baseScale*1.2
        v = height - 50
        v -= spacing*1.15
        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=baseScale,
                                              stackOffset=(0,-30) if gSmallUI else (0,0))

        backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(35,height-50),size=(120,60),scale=0.8,textScale=1.2,autoSelect=True,
                            label=bs.getResource('backText'),buttonType='back',onActivateCall=self._back)

        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(0,height-44),size=(width,25),text=R.titleText,color=gTitleColor,
                          hAlign="center",vAlign="top")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(100,height-37))
        
        if self._showFullscreen:
            v -= fullscreenSpacingTop
            self._fullscreenCheckBox = configCheckBox(parent=self._rootWidget,position=(100,v),maxWidth=200,
                                                      size=(300,30),name="Fullscreen",displayName=R.fullScreenCmdText if 'Mac' in ua else R.fullScreenCtrlText)
            if not self._haveSelectedChild:
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._fullscreenCheckBox)
                self._haveSelectedChild = True
            v -= fullscreenSpacing
        else:
            self._fullscreenCheckBox = None

        if showGamma:
            self._gammaControls = tb = configTextBox(parent=self._rootWidget,position=(90,v),
                                                     name="Screen Gamma",displayName=R.gammaText,
                                                     type="float",minVal=0.1,maxVal=2.0,
                                                     increment=0.1,xOffset=-70,textScale=0.85)
            if not self._haveSelectedChild:
                bs.containerWidget(edit=self._rootWidget,selectedChild=tb)
                self._haveSelectedChild = True
            v -= gammaSpacing
        else:
            self._gammaControls = None

        self._selectedColor=(0.5,1,0.5,1)
        self._unselectedColor=(0.7,0.7,0.7,1)

        # quality
        hOffs = 15
        t = bs.textWidget(parent=self._rootWidget,position=(60,v),size=(160,25),
                          text=R.visualsText,
                          color=gHeadingColor,scale=0.65,maxWidth=150,
                          hAlign="center",vAlign="center")
        visualsPopup = PopupMenu(parent=self._rootWidget,position=(60,v-50),width=150,scale=popupMenuScale,
                                 choices=['Auto','Higher','High','Medium','Low'],
                                 choicesDisabled=['Higher','High'] if bsInternal._getMaxGraphicsQuality() == 'Medium' else [],
                                 choicesDisplay=[bs.getResource('autoText'),R.higherText,R.highText,R.mediumText,R.lowText],
                                 currentChoice=bsInternal._getSetting('Graphics Quality'),onValueChangeCall=self._setQuality)

        # texture controls
        hOffs = 210
        t = bs.textWidget(parent=self._rootWidget,position=(230,v),size=(160,25),
                          text=R.texturesText,
                          color=gHeadingColor,scale=0.65,maxWidth=150,
                          hAlign="center",vAlign="center")
        texturesPopup = PopupMenu(parent=self._rootWidget,position=(230,v-50),width=150,scale=popupMenuScale,
                                  choices=['Auto','High','Medium','Low'],
                                  choicesDisplay=[bs.getResource('autoText'),R.highText,R.mediumText,R.lowText],
                                  currentChoice=bsInternal._getSetting('Texture Quality'),onValueChangeCall=self._setTextures)

        v -= 80

        hOffs = 0

        if showResolution:
            # resolution
            t = bs.textWidget(parent=self._rootWidget,position=(hOffs+60,v),size=(160,25),
                              text=R.resolutionText,
                              color=gHeadingColor,scale=0.65,maxWidth=150,
                              hAlign="center",vAlign="center")


            # on android we have 'Auto', 'Native', and a few HD standards
            if env['platform'] == 'android':
                nativeRes = bsInternal._getDisplayResolution()
                choices = ['Auto','Native']
                choicesDisplay = [bs.getResource('autoText'),bs.getResource('nativeText')]
                #choicesDisabled = []
                for res in [1440,1080,960,720,480]:
                    # nav bar is 72px so lets allow for that in what choices we show
                    if nativeRes[1] >= res-72:
                        resStr = str(res)+'p'
                        choices.append(resStr)
                        choicesDisplay.append(resStr)
                # if (nativeRes[1] < 1440-72): choicesDisabled.append('1440p')
                # if (nativeRes[1] < 1080-72): choicesDisabled.append('1080p')
                # if (nativeRes[1] < 960-72): choicesDisabled.append('960p')
                # if (nativeRes[1] < 720-72): choicesDisabled.append('720p')
                # if (nativeRes[1] < 480-72): choicesDisabled.append('480p')
                currentRes = bsInternal._getSetting('Resolution (Android)')
                resPopup = PopupMenu(parent=self._rootWidget,position=(hOffs+60,v-50),width=120,scale=popupMenuScale,
                                     choices=choices,choicesDisplay=choicesDisplay,
                                     #choices=['Auto','Native','1440p','1080p','960p','720p','480p'],
                                     #choicesDisplay=[bs.getResource('autoText'),bs.getResource('nativeText'),'1440p','1080p','960p','720p','480p'],
                                     #choicesDisabled=choicesDisabled,
                                     currentChoice=currentRes,onValueChangeCall=self._setAndroidRes)

            else:

                # if we're on a system that doesn't allow setting resolution, set pixel-scale instead
                currentRes = bsInternal._getDisplayResolution()
                if currentRes is None:
                    currentRes = str(min(100,max(10,int(round(bsInternal._getSetting('Screen Pixel Scale')*100.0)))))+'%'
                    resPopup = PopupMenu(parent=self._rootWidget,position=(hOffs+60,v-50),width=120,scale=popupMenuScale,
                                         choices=['100%','88%','75%','63%','50%'],
                                         currentChoice=currentRes,onValueChangeCall=self._setPixelScale)
                else:
                    resolutions = bsInternal._getDisplayResolutions()
                    resList = ['Desktop Res']+resolutions
                    resListDisplay = [bs.getResource('desktopResText')]+resolutions
                    resPopup = PopupMenu(parent=self._rootWidget,position=(hOffs+60,v-50),scale=popupMenuScale,
                                         choices=resList,
                                         choicesDisplay=resListDisplay,
                                         currentChoice=currentRes,onValueChangeCall=self._setRes)
                    self._resPopup = weakref.ref(resPopup)
        hOffs = 210

        # vsync
        if showVSync:
            t = bs.textWidget(parent=self._rootWidget,position=(230,v),
                              size=(160,25),text=R.verticalSyncText,
                              color=gHeadingColor,scale=0.65,maxWidth=150,
                              hAlign="center",vAlign="center")

            vSyncPopup = PopupMenu(parent=self._rootWidget,position=(230,v-50),width=150,scale=popupMenuScale,
                                   choices=['Auto','Always','Never'],
                                   choicesDisplay=[bs.getResource('autoText'),R.alwaysText,R.neverText],
                                   currentChoice=bsInternal._getSetting('Vertical Sync'),onValueChangeCall=self._setVSync)
        else: vSyncPopup = None

        v -= 90
        fpsc = configCheckBox(parent=self._rootWidget,position=(69,v-6),
                              size=(210,30),scale=0.86,name="Show FPS",displayName=R.showFPSText,maxWidth=130)

        # (tv mode doesnt apply to vr)
        if not bs.getEnvironment()['vrMode']:
            tvc = configCheckBox(parent=self._rootWidget,position=(240,v-6),
                                  size=(210,30),scale=0.86,name="TV Border",displayName=R.tvBorderText,maxWidth=130)
            # grumble..
            bs.widget(edit=fpsc,rightWidget=tvc)

        try:
            pass
            # resB = resPopup.getButtonWidget()
            # visB = visualsPopup.getButtonWidget()
            # texB = texturesPopup.getButtonWidget()

            # if self._gammaControls is not None:
            #     if self._fullscreenCheckBox is not None:
            #         bs.widget(edit=self._gammaControls['minusButton'],upWidget=self._fullscreenCheckBox)
            #         bs.widget(edit=self._gammaControls['plusButton'],upWidget=self._fullscreenCheckBox)
            #     else:
            #         bs.widget(edit=self._gammaControls['minusButton'],upWidget=backButton)
            #         bs.widget(edit=self._gammaControls['plusButton'],upWidget=backButton)
            #     bs.widget(edit=self._gammaControls['minusButton'],downWidget=texB)
            #     bs.widget(edit=self._gammaControls['plusButton'],downWidget=texB)
            #     bs.widget(edit=texB,upWidget=self._gammaControls['plusButton'])
            #     bs.widget(edit=visB,upWidget=self._gammaControls['minusButton'])

            # # no gamma controls
            # else:
            #     if self._fullscreenCheckBox is not None:
            #         bs.widget(edit=self._fullscreenCheckBox,rightWidget=texB)
            #         bs.widget(edit=texB,upWidget=self._fullscreenCheckBox)
            #         bs.widget(edit=visB,upWidget=self._fullscreenCheckBox)
            #     else:
            #         bs.widget(edit=texB,upWidget=backButton)

            # bs.widget(edit=visB,downWidget=resB)
            # bs.widget(edit=resB,upWidget=visB,downWidget=fpsc)
            # bs.widget(edit=fpsc,upWidget=resB)
            # if vSyncPopup is not None:
            #     vsB = vSyncPopup.getButtonWidget()
            #     bs.widget(edit=vsB,upWidget=texB,downWidget=tvc)
            #     bs.widget(edit=texB,downWidget=vsB)
            #     bs.widget(edit=tvc,upWidget=vsB)
            # else:
            #     bs.widget(edit=texB,downWidget=tvc)
            #     bs.widget(edit=tvc,upWidget=texB)

        except Exception:
            bs.printException('Exception wiring up graphics settings UI:')

        # fpsc = configCheckBox(parent=self._rootWidget,position=(150,v-7) if showVSync else (243,v+49),
        #                       size=(210,30),scale=1.0 if showVSync else 0.85,name="Show FPS")
        v -= spacing

        # make a timer to update our controls in case the config changes under us
        self._updateTimer = bs.Timer(250,bs.WeakCall(self._updateControls),repeat=True,timeType='real')

    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = SettingsWindow(transition='inLeft').getRootWidget()

    def _setQuality(self,quality):
        bs.getConfig()['Graphics Quality'] = quality
        bs.applySettings()
        bs.writeConfig()

    def _setTextures(self,val):
        bs.getConfig()['Texture Quality'] = val
        bs.applySettings()
        bs.writeConfig()

    def _setAndroidRes(self,val):
        #print 'PY SET RES',val
        bs.getConfig()['Resolution (Android)'] = val
        bs.writeConfig()
        bs.applySettings()
        
    def _setPixelScale(self,res):
        bs.getConfig()['Screen Pixel Scale'] = float(res[:-1])/100.0
        bs.writeConfig()
        bs.applySettings()
        
    def _setRes(self,res,confirm=True,playSound=False):
        self._oldRes = bsInternal._getDisplayResolution()

        if playSound: bs.playSound(bs.getSound('swish'))

        bs.getConfig()['Screen Resolution'] = res

        bs.writeConfig()
        bs.applySettings()

        rp = self._resPopup()
        if rp is not None: rp.setChoice(res)

        # if we're changing resolution in fullscreen mode, bring up a confirmation window to make sure the res is visible
        if self._oldRes != res and confirm and bsInternal._getSetting('Fullscreen'):
            ResChangeConfirmWindow(self)

    def _setVSync(self,val):
        bs.getConfig()['Vertical Sync'] = val
        bs.applySettings()
        bs.writeConfig()

    def _updateControls(self):
        if self._showFullscreen:
            bs.checkBoxWidget(edit=self._fullscreenCheckBox,value=bsInternal._getSetting('Fullscreen'))

class ResChangeConfirmWindow(object):

    def __init__(self,configGraphicsWindow):
        self._configGraphicsWindow = configGraphicsWindow
        width = 550
        height = 200
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight')
        self._confirmCounter = 10
        t = bs.textWidget(parent=self._rootWidget,position=(15,height-80),size=(width-30,30),
                          text=bs.getResource('keepTheseSettingsText'),
                          maxWidth=width*0.95,
                          color=(0,1,0,1),
                          scale=1.3,
                          hAlign="center",vAlign="center")
        self._timeText = bs.textWidget(parent=self._rootWidget,position=(15,40),size=(width-30,30),
                                       text=("10"),
                                       hAlign="center",vAlign="top")
        self._revertButton = b = bs.buttonWidget(parent=self._rootWidget,position=(25,40),size=(160,50),label=bs.getResource('revertText'),onActivateCall=self._revert)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        b = bs.buttonWidget(parent=self._rootWidget,position=(width-190,40),size=(160,50),label=bs.getResource('keepText'),onActivateCall=self._keep)
        self._timer = bs.Timer(1000,bs.WeakCall(self._tick),repeat=True,timeType='real')

    def _keep(self):
        self._timer = None
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _revert(self):
        self._timer = None
        self._configGraphicsWindow._setRes(self._configGraphicsWindow._oldRes,confirm=False,playSound=True)
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _tick(self):
        self._confirmCounter -= 1
        bs.textWidget(edit=self._timeText,text=str(self._confirmCounter))
        if self._confirmCounter == 0:
            self._revertButton.activate()

def _promoCodeCallback(data):
    if data is None:
        bs.screenMessage(bs.getResource('promoSubmitErrorText'),color=(1,0,0))
        bs.playSound(bs.getSound('error'))
    else:
        if data['success']:
            bs.screenMessage(bs.translate('promoCodeResponses',data['message']),color=(0,1,0))
            bs.playSound(bs.getSound('ding'))
        else:
            bs.screenMessage(bs.translate('promoCodeResponses',data['message']),color=(1,0,0))
            bs.playSound(bs.getSound('error'))

class PromoCodeWindow(Window):
    def __init__(self,transition='inRight',modal=False,originWidget=None):

        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
            transition = 'inRight'
        
        width = 450
        height = 230
        spacing = 32

        self._modal = modal
        R = bs.getResource('promoCodeWindow')

        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=2.0 if gSmallUI else 1.5 if gMedUI else 1.0)
        # b = bs.buttonWidget(parent=self._rootWidget,position=(35,height-55),size=(140,60),scale=0.8,
        #                     label=bs.getResource('cancelText'),onActivateCall=self._doBack)

        b = bs.buttonWidget(parent=self._rootWidget,scale=0.5,position=(40,height-40),size=(60,60),
                            label='',onActivateCall=self._doBack,autoSelect=True,
                            color=(0.55,0.5,0.6),
                            icon=bs.getTexture('crossOut'),iconScale=1.2)
        
        bs.textWidget(parent=self._rootWidget,text=R.codeText,position=(22,height-113),color=(0.8,0.8,0.8,1.0),size=(90,30),hAlign='right')
        self._textField = bs.textWidget(parent=self._rootWidget,position=(125,height-121),size=(280,46),
                                        text='',hAlign="left",
                                        vAlign="center",
                                        maxChars=64,
                                        color=(0.9,0.9,0.9,1.0),
                                        description=R.codeText,
                                        editable=True,padding=4,
                                        onReturnPressCall=self._activateEnterButton)
        bs.widget(edit=b,downWidget=self._textField)

        bWidth = 200
        self._enterButton = b2 = bs.buttonWidget(parent=self._rootWidget,position=(width*0.5-bWidth*0.5,height-200),size=(bWidth,60),scale=1.0,
                            label=R.enterText,onActivateCall=self._doEnter)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b,startButton=b2,selectedChild=self._textField)

    def _doBack(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if not self._modal:
            uiGlobals['mainMenuWindow'] = AdvancedSettingsWindow(transition='inLeft').getRootWidget()

    def _activateEnterButton(self):
        self._enterButton.activate()

    def _doEnter(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if not self._modal:
            uiGlobals['mainMenuWindow'] = AdvancedSettingsWindow(transition='inLeft').getRootWidget()
        bsInternal._addTransaction({'type':'PROMO_CODE',
                                    'expireTime':time.time()+5,
                                    'code':bs.textWidget(query=self._textField)})
        bsInternal._runTransactions()

gValueTestDefaults = {}

class TestingWindow(Window):
    def __init__(self,title,entries,transition='inRight'):
        global gValueTestDefaults
        self._width = 600
        self._height = 324 if gSmallUI else 400
        self._entries = copy.deepcopy(entries)
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scale=2.5 if gSmallUI else 1.2 if gMedUI else 1.0,
                                              stackOffset=(0,-28) if gSmallUI else (0,0))
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(65,self._height-59),size=(130,60),scale=0.8,textScale=1.2,
                            label=bs.getResource('backText'),buttonType='back',onActivateCall=self._doBack)
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-35),size=(0,0),color=gTitleColor,
                          hAlign='center',vAlign='center', maxWidth=245,text=title)

        if gDoAndroidNav:
            bs.buttonWidget(edit=self._backButton,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(118,self._height-35))
        
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-75),size=(0,0),color=gInfoTextColor,
                          hAlign='center',vAlign='center', maxWidth=self._width*0.75,text=bs.getResource('settingsWindowAdvanced.forTestingText'))
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        self._scrollWidth = self._width - 130
        self._scrollHeight = self._height - 140
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._scrollWidth,self._scrollHeight),
                                             highlight=False, position=((self._width-self._scrollWidth)*0.5,40))
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)

        self._spacing = 50
        
        self._subWidth = self._scrollWidth*0.95
        self._subHeight = 50 + len(self._entries)*self._spacing + 60
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),background=False)

        h = 230
        v = self._subHeight - 48
        
        for i,entry in enumerate(self._entries):

            entryName = entry['name']
            
            # if we havn't yet, record the default value for this name so we can reset if we want..
            if not entryName in gValueTestDefaults:
                gValueTestDefaults[entryName] = bsInternal._valueTest(entryName)
                #print 'STORING DEFAULT FOR',entryName,'of',gValueTestDefaults[entryName]
                
            t = bs.textWidget(parent=self._subContainer,position=(h,v),size=(0,0),
                              hAlign='right',vAlign='center', maxWidth=200,text=entry['label'])
            b = bs.buttonWidget(parent=self._subContainer,position=(h+20,v-19),size=(40,40),autoSelect=True,repeat=True,
                                leftWidget=self._backButton,buttonType='square',label='-',onActivateCall=bs.Call(self._onMinusPress,entry['name']))
            if i == 0: bs.widget(edit=b,upWidget=self._backButton)
            bs.widget(edit=b,showBufferTop=20,showBufferBottom=20)
            entry['widget'] = t = bs.textWidget(parent=self._subContainer,position=(h+100,v),size=(0,0),
                                                hAlign='center',vAlign='center', maxWidth=60,text=str(round(bsInternal._valueTest(entryName),4)))
            b = bs.buttonWidget(parent=self._subContainer,position=(h+140,v-19),size=(40,40),autoSelect=True,repeat=True,
                                buttonType='square',label='+',onActivateCall=bs.Call(self._onPlusPress,entry['name']))
            if i == 0: bs.widget(edit=b,upWidget=self._backButton)
            v -= self._spacing
        v -= 35
        bReset = bs.buttonWidget(parent=self._subContainer,autoSelect=True,size=(200,50),position=(self._subWidth*0.5-100,v),
                                 label=bs.getResource('settingsWindowAdvanced.resetText'),rightWidget=b,onActivateCall=self._onResetPress)
        bs.widget(edit=bReset,showBufferTop=20,showBufferBottom=20)

    def _getEntry(self,name):
        for entry in self._entries:
            if entry['name'] == name: return entry
            
    def _onResetPress(self):
        for entry in self._entries:
            val = bsInternal._valueTest(entry['name'],absolute=gValueTestDefaults[entry['name']])
            bs.textWidget(edit=entry['widget'],text=str(round(bsInternal._valueTest(entry['name']),4)))
            
    def _onMinusPress(self,entryName):
        entry = self._getEntry(entryName)
        val = bsInternal._valueTest(entry['name'],change=-entry['increment'])
        bs.textWidget(edit=entry['widget'],text=str(round(bsInternal._valueTest(entry['name']),4)))

    def _onPlusPress(self,entryName):
        entry = self._getEntry(entryName)
        val = bsInternal._valueTest(entry['name'],change=entry['increment'])
        bs.textWidget(edit=entry['widget'],text=str(round(bsInternal._valueTest(entry['name']),4)))
        
    def _doBack(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = AdvancedSettingsWindow(transition='inLeft').getRootWidget()

class VRTestingWindow(TestingWindow):
    def __init__(self,transition='inRight'):

        entries = []
        env = bs.getEnvironment()
        # these are gear-vr only
        if env['platform'] == 'android' and env['subplatform'] == 'oculus':
            entries += [
                {'name':'timeWarpDebug','label':'Time Warp Debug','increment':1.0},
                {'name':'chromaticAberrationCorrection','label':'Chromatic Aberration Correction','increment':1.0},
                # {'name':'vrIntensityScaleByArea','label':'Show Vignette','increment':1.0},
                {'name':'vrCPUSpeed','label':'CPU Level','increment':1.0},
                {'name':'vrGPUSpeed','label':'GPU Level','increment':1.0},
                {'name':'vrMultisamples','label':'Multisamples','increment':1.0},
                {'name':'vrColorBitDepth','label':'Color Bits','increment':1.0},
                {'name':'vrDepthBitDepth','label':'Depth Bits','increment':1.0},
                {'name':'vrResolution','label':'Resolution','increment':1.0},
                {'name':'vrMinimumVSyncs','label':'Minimum Vsyncs','increment':1.0},
                {'name':'eyeOffsX','label':'Eye IPD','increment':0.001}
                ]
        # cardboard/gearvr get eye offset controls..
        if env['platform'] == 'android':
            entries += [
                {'name':'eyeOffsY','label':'Eye Offset Y','increment':0.01},
                {'name':'eyeOffsZ','label':'Eye Offset Z','increment':0.005}]
        # everyone gets head-scale
        entries += [ {'name':'headScale','label':'Head Scale','increment':1.0}]
        # cardboard/gearvr gets fov-scale
        if env['platform'] == 'android':
            entries += [{'name':'stereoFOVScale','label':'FOV Scale','increment':0.01}]
        # and everyone gets all these..
        entries += [
            {'name':'vrCamOffsetY','label':'In-Game Cam Offset Y','increment':0.1},
            {'name':'vrCamOffsetZ','label':'In-Game Cam Offset Z','increment':0.1},
            {'name':'vrOverlayScale','label':'Overlay Scale','increment':0.05},
            {'name':'allowCameraMovement','label':'Allow Camera Movement','increment':1.0},
            {'name':'cameraPanSpeedScale','label':'Camera Movement Speed','increment':0.1},
            {'name':'showOverlayBounds','label':'Show Overlay Bounds','increment':1},
        ]

        TestingWindow.__init__(self,bs.getResource('settingsWindowAdvanced.vrTestingText'),entries,transition)
        
        # v = self._height - 130
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='eyeOffsX -',size=(200,60),
        #                 position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'eyeOffsX',-0.1))
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='eyeOffsX +',size=(200,60),
        #                 position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'eyeOffsX',0.1))
        # v -= 70
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='eyeOffsY -',size=(200,60),
        #                 position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'eyeOffsY',-0.1))
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='eyeOffsY +',size=(200,60),
        #                 position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'eyeOffsY',0.1))
        # v -= 70
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='eyeOffsZ -',size=(200,60),
        #                 position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'eyeOffsZ',-0.1))
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='eyeOffsZ +',size=(200,60),
        #                 position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'eyeOffsZ',0.1))
        # v -= 70
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='headScale -',size=(200,60),
        #                 position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'headScale',-0.05))
        # bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='headScale +',size=(200,60),
        #                 position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'headScale',0.05))
        
        
class NetTestingWindow(TestingWindow):
    def __init__(self,transition='inRight'):

        entries = [{'name':'bufferTime','label':'Buffer Time','increment':1.0},
                   {'name':'delaySampling','label':'Delay Sampling','increment':1.0},
                   {'name':'dynamicsSyncTime','label':'Dynamics Sync Time','increment':10},
                   {'name':'showNetInfo','label':'Show Net Info','increment':1},
                   ]
        TestingWindow.__init__(self,bs.getResource('settingsWindowAdvanced.netTestingText'),entries,transition)
    #     self._width = 500
    #     self._height = 300
    #     self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,scale=1.8)
    #     self._backButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(30,self._height-54),size=(130,60),scale=0.8,textScale=1.2,
    #                         label=bs.getResource('backText'),buttonType='back',onActivateCall=self._doBack)
    #     bs.containerWidget(edit=self._rootWidget,cancelButton=b)

    #     v = self._height - 130
    #     bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='bufferTime -',size=(200,60),
    #                     position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'bufferTime',-1))
    #     bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='bufferTime +',size=(200,60),
    #                     position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'bufferTime',1))
    #     v -= 70
    #     bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='delaySampling -',size=(200,60),
    #                     position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'delaySampling',-1))
    #     bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='delaySampling +',size=(200,60),
    #                     position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'delaySampling',1))
    #     v -= 70
    #     bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='dynamicsSyncTime -',size=(200,60),
    #                     position=(35,v),onActivateCall=bs.Call(bsInternal._valueTest,'dynamicsSyncTime',-10))
    #     bs.buttonWidget(parent=self._rootWidget,autoSelect=True,label='dynamicsSyncTime +',size=(200,60),
    #                     position=(255,v),onActivateCall=bs.Call(bsInternal._valueTest,'dynamicsSyncTime',10))
        
    # def _doBack(self):
    #     bs.containerWidget(edit=self._rootWidget,transition='outRight')



        
        
class AdvancedSettingsWindow(Window):

    # def __del__(self):
    #     print '~AdvancedSettingsWindow()'
        
    def __init__(self,transition='inRight',originWidget=None):

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._width = 670
        self._height = 390 if gSmallUI else 450 if gMedUI else 520
        self._spacing = 32
        self._menuOpen = False
        topExtra = 10 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=2.06 if gSmallUI else 1.4 if gMedUI else 1.0,
                                              stackOffset=(0,-25) if gSmallUI else (0,0))
        self._prevLang = ""
        self._prevLangList = []
        self._completeLangsList = None
        self._completeLangsError = False
        self._languagePopup = None

        # in vr-mode, the internal keyboard is currently the *only* option, so no need to show this..
        self._showAlwaysUseInternalKeyboard = False if bs.getEnvironment()['vrMode'] else True
        
        self._scrollWidth = self._width - 100
        self._scrollHeight = self._height - 115
        self._subWidth = self._scrollWidth*0.95
        self._subHeight = 732+8+60-60
        
        if self._showAlwaysUseInternalKeyboard: self._subHeight += 62

        self._doVRTestButton = True if bs.getEnvironment()['vrMode'] else False
        
        self._doNetTestButton = True

        self._extraButtonSpacing = self._spacing * 2.5
        
        if self._doVRTestButton: self._subHeight += self._extraButtonSpacing
        if self._doNetTestButton: self._subHeight += self._extraButtonSpacing
        
        self._R = R = bs.getResource('settingsWindowAdvanced')
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(53,self._height-60),size=(140,60),scale=0.8,
                                                            autoSelect=True,label=bs.getResource('backText'),buttonType='back',onActivateCall=self._doBack)

        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        self._titleText = t = bs.textWidget(parent=self._rootWidget,position=(0,self._height-52),size=(self._width,25),text=R.titleText,color=gTitleColor,
                                            hAlign="center",vAlign="top")

        if gDoAndroidNav:
            bs.buttonWidget(edit=self._backButton,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(115,self._height-47))
            
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(50,50),simpleCullingV=20.0,
                                             highlight=False, size=(self._scrollWidth,self._scrollHeight))
        bs.containerWidget(edit=self._scrollWidget,selectionLoopToParent=True)
        self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),
                                                    background=False,selectionLoopToParent=True)

        
        self._rebuild()
            
        # rebuild periodically to pick up language changes/additions/etc
        self._rebuildTimer = bs.Timer(1000,bs.WeakCall(self._rebuild),repeat=True,timeType='real')

        # fetch the list of completed languages
        bsUtils.serverGet('bsLangGetCompleted',{},callback=bs.WeakCall(self._completedLangsCB))
    
    def _updateLangStatus(self):
        if self._completeLangsList is not None:
            upToDate = (bs.getLanguage() in self._completeLangsList)
            t = bs.textWidget(edit=self._langStatusText,text='' if bs.getLanguage() == 'Test' else self._R.translationNoUpdateNeededText if upToDate else self._R.translationUpdateNeededText,
                              color=(0.2,1.0,0.2,0.8) if upToDate else (1.0,0.2,0.2,0.8))
        else:
            t = bs.textWidget(edit=self._langStatusText,
                              text=self._R.translationFetchErrorText if self._completeLangsError else self._R.translationFetchingStatusText,
                              color=(1.0,0.5,0.2) if self._completeLangsError else (0.7,0.7,0.7))
            

    def _rebuild(self):

        # dont rebuild if the menu is open or if our language and language-list hasn't changed
        if self._menuOpen or (self._prevLang == bs.getLanguage(returnNoneForDefault=True) and self._prevLangList == bsUtils._getLanguages()): return
        self._prevLang = bs.getLanguage(returnNoneForDefault=True)
        self._prevLangList = bsUtils._getLanguages()

        # if our popup menu was selected we wanna restore that..
        #langWasSelected = (self._languagePopup is not None and self._subContainer.getSelectedChild() == self._languagePopup.getButtonWidget())

        # clear out our sub-container
        children = self._subContainer.getChildren()
        for c in children: c.delete()

        
        v = self._subHeight - 35


        v -= self._spacing * 1.2

        # TEMP
        # testButton = None
        # if bs.getEnvironment()['vrMode']:
        #     testButton = b = bs.buttonWidget(parent=self._subContainer,autoSelect=True,label='VR TESTING',size=(150,60),
        #                                      position=(self._subWidth-190,self._subHeight-65),onActivateCall=VRTestingWindow)
        # testButton = b = bs.buttonWidget(parent=self._subContainer,autoSelect=True,label='NET TESTING',size=(150,60),
        #                     position=(self._subWidth-190,self._height-65),onActivateCall=NetTestingWindow)

        
        # spn = configCheckBox(parent=self._subContainer,position=(100,v),size=(self._subWidth-100,30),name="Show Player Names",
        #                      displayName=R.showPlayerNamesText,scale=1.0,maxWidth=340)

        # gotta re-fetch this cuz language probably changed
        self._R = R = bs.getResource('settingsWindowAdvanced')

        # update our existing back button and title
        bs.buttonWidget(edit=self._backButton,label=bs.getResource('backText'))
        if gDoAndroidNav: bs.buttonWidget(edit=self._backButton,label=bs.getSpecialChar('back'))
        
        bs.textWidget(edit=self._titleText,text=R.titleText)
        

        thisButtonWidth = 410

        self._promoCodeButton = bs.buttonWidget(parent=self._subContainer,
                                                position=(self._subWidth/2-thisButtonWidth/2,v-14),
                                                size=(thisButtonWidth,60),
                                                autoSelect=True,
                                                label=R.enterPromoCodeText,
                                                textScale=1.0,
                                                onActivateCall=self._onPromoCodePress)
        bs.widget(edit=self._promoCodeButton,upWidget=self._backButton,leftWidget=self._backButton)
        v -= self._extraButtonSpacing * 0.8

        # self._friendPromoCodeButton = bs.buttonWidget(parent=self._subContainer,
        #                                               position=(self._subWidth/2-thisButtonWidth/2,v-14),
        #                                               size=(thisButtonWidth,50),
        #                                               autoSelect=True,
        #                                               label=bs.getResource('gatherWindow.getFriendInviteCodeText'),
        #                                               textScale=1.0,
        #                                               onActivateCall=self._onFriendPromoCodePress)
        # v -= self._extraButtonSpacing * 1.05
        

        t = bs.textWidget(parent=self._subContainer,position=(200,v+10),size=(0,0),text=R.languageText,maxWidth=150,
                          scale=0.95*R.languageTextScale,color=gTitleColor,hAlign='right',vAlign='center')

        languages = bsUtils._getLanguages()
        curLang = bs.getLanguage(returnNoneForDefault=True)
        if curLang is None: curLang = 'Auto'

        # we have a special dict of language names in that language
        # so we dont have to import every language module here..
        # (that causes hitches on slower systems)
        langsTranslated = {}
        for lang in languages:
            langsTranslated[lang] = lang # default
            if lang in bsServerData.languageNamesTranslated:
                langsTranslated[lang] = bs.uni(bsServerData.languageNamesTranslated[lang])

        langsFull = {}
        for lang in languages:
            lt = bs.translate('languages',lang,printErrors=False)
            if langsTranslated[lang] == lt:
                langsFull[lang] = lt
            else: langsFull[lang] = langsTranslated[lang]+' ('+lt+')'

        self._languagePopup = PopupMenu(parent=self._subContainer,position=(210,v-19),width=150,
                                        openingCall=bs.WeakCall(self._onMenuOpen),closingCall=bs.WeakCall(self._onMenuClose),autoSelect=False,
                                        onValueChangeCall=bs.WeakCall(self._onMenuChoice),
                                        choices=['Auto']+languages,buttonSize=(250,60),
                                        choicesDisplay=([bs.getResource('autoText')+' ('+bs.translate('languages',bsUtils._getDefaultLanguage())+')']
                                                        +[langsFull[l] for l in languages]),
                                        currentChoice=curLang)

        # bs.widget(edit=self._alwaysUseInternalKeyboardCheckBox if self._showAlwaysUseInternalKeyboard else self._kickIdlePlayersCheckBox,
        #           downWidget=self._languagePopup.getButtonWidget())
        # if langWasSelected:
        #     bs.containerWidget(edit=self._subContainer,selectedChild=self._languagePopup.getButtonWidget())
            
        v -= self._spacing * 1.8

        t = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v+10),size=(0,0),text=R.helpTranslateText.replace('${APP_NAME}',bs.getResource('titleText')),
                          maxWidth=self._subWidth*0.9,maxHeight=55,
                          flatness=1.0,scale=0.65*R.helpTranslateTextScale,color=(0.4,0.9,0.4,0.8),hAlign='center',vAlign='center')
        v -= self._spacing * 1.9
        thisButtonWidth = 410
        self._translationEditorButton = bs.buttonWidget(parent=self._subContainer,
                                                        position=(self._subWidth/2-thisButtonWidth/2,v-24),
                                                        size=(thisButtonWidth,60),
                                                        label=R.translationEditorButtonText.replace('${APP_NAME}',bs.getResource('titleText')),
                                                        autoSelect=True,
                                                        onActivateCall=bs.Call(bs.openURL,'http://bombsquadgame.com/translate'))

        self._langStatusText = bs.textWidget(parent=self._subContainer,position=(self._subWidth*0.5,v-40),size=(0,0),
                                             text='',flatness=1.0,
                                             scale=0.63,
                                             hAlign='center',vAlign='center',maxWidth=400.0)
        self._updateLangStatus()
        v -= self._spacing * 3.0

        #v -= self._spacing * 1.0
        self._kidFriendlyCheckBox = cb = configCheckBox(parent=self._subContainer,position=(50,v),size=(self._subWidth-100,30),name="Kid Friendly Mode",
                                                        displayName=R.kidFriendlyModeText,scale=1.0,maxWidth=430)
        bs.widget(edit=self._translationEditorButton,downWidget=cb, upWidget=self._languagePopup.getButtonWidget())
        # bs.widget(edit=cb,upWidget=self._backButton,leftWidget=self._backButton)

        # if testButton is not None:
        #     bs.widget(edit=backButton,rightWidget=testButton,downWidget=cb)
        #     bs.widget(edit=testButton,leftWidget=backButton,downWidget=cb)
        
        v -= self._spacing * 1.2
        self._kickIdlePlayersCheckBox = configCheckBox(parent=self._subContainer,position=(50,v),size=(self._subWidth-100,30),name="Kick Idle Players",autoSelect=True,
                                                       displayName=R.kickIdlePlayersText,scale=1.0,maxWidth=430)

        if self._showAlwaysUseInternalKeyboard:
            v -= 42
            self._alwaysUseInternalKeyboardCheckBox = configCheckBox(parent=self._subContainer,position=(50,v),size=(self._subWidth-100,30),name="Always Use Internal Keyboard",
                                                                     autoSelect=True,
                                                                     displayName=R.alwaysUseInternalKeyboardText,scale=1.0,maxWidth=430)
            t = bs.textWidget(parent=self._subContainer,position=(90,v-10),size=(0,0),
                              text=R.alwaysUseInternalKeyboardDescriptionText,
                              maxWidth=400,flatness=1.0,scale=0.65,color=(0.4,0.9,0.4,0.8),
                              hAlign='left',vAlign='center')
            v -= 20
        else: self._alwaysUseInternalKeyboardCheckBox = None

        
        v -= self._spacing * 2.1
        

        thisButtonWidth = 410
        self._showUserModsButton = bs.buttonWidget(parent=self._subContainer,
                                                   position=(self._subWidth/2-thisButtonWidth/2,v-10),
                                                   size=(thisButtonWidth,60),
                                                   autoSelect=True,
                                                   label=R.showUserModsText,
                                                   textScale=1.0,
                                                   onActivateCall=bsUtils.showUserScripts)
        if self._showAlwaysUseInternalKeyboard:
            bs.widget(edit=self._alwaysUseInternalKeyboardCheckBox,downWidget=self._showUserModsButton)
            bs.widget(edit=self._showUserModsButton,upWidget=self._alwaysUseInternalKeyboardCheckBox)
        else:
            bs.widget(edit=self._showUserModsButton,upWidget=self._kickIdlePlayersCheckBox)
            bs.widget(edit=self._kickIdlePlayersCheckBox,downWidget=self._showUserModsButton)
            
            
        v -= self._spacing * 2.0
        
        b = self._moddingGuideButton = bs.buttonWidget(parent=self._subContainer,
                                                       position=(self._subWidth/2-thisButtonWidth/2,v-10),
                                                       size=(thisButtonWidth,60),
                                                       autoSelect=True,
                                                       label=R.moddingGuideText,
                                                       textScale=1.0,
                                                       onActivateCall=bs.Call(bs.openURL,'http://www.froemling.net/docs/bombsquad-modding-guide'))

        v -= self._spacing * 1.8

        def foo(val):
            bs.screenMessage(self._R.mustRestartText,color=(1,1,0))
            
        cb = self._enablePackageModsCheckBox = configCheckBox(parent=self._subContainer,position=(80,v),size=(self._subWidth-100,30),
                                                               name="Enable Package Mods",autoSelect=True,valueChangeCall=foo,
                                                               displayName=R.enablePackageModsText,scale=1.0,maxWidth=400)
        bs.widget(edit=b,downWidget=cb)
        bs.widget(edit=cb,upWidget=b)
        t = bs.textWidget(parent=self._subContainer,position=(90,v-10),size=(0,0),
                          text=R.enablePackageModsDescriptionText,
                          maxWidth=400,flatness=1.0,scale=0.65,color=(0.4,0.9,0.4,0.8),
                          hAlign='left',vAlign='center')
        
        v -= self._spacing * 0.6

        if self._doVRTestButton:
            v -= self._extraButtonSpacing
            self._vrTestButton = bs.buttonWidget(parent=self._subContainer,
                                                 position=(self._subWidth/2-thisButtonWidth/2,v-14),
                                                 size=(thisButtonWidth,60),
                                                 autoSelect=True,
                                                 label=R.vrTestingText,
                                                 textScale=1.0,
                                                 onActivateCall=self._onVRTestPress)
        else:
            self._vrTestButton = None
            
        if self._doNetTestButton:
            v -= self._extraButtonSpacing
            self._netTestButton = bs.buttonWidget(parent=self._subContainer,
                                                  position=(self._subWidth/2-thisButtonWidth/2,v-14),
                                                  size=(thisButtonWidth,60),
                                                  autoSelect=True,
                                                  label=R.netTestingText,
                                                  textScale=1.0,
                                                  onActivateCall=self._onNetTestPress)
        else: self._netTestButton = None

        v -= 70
        self._benchmarksButton = bs.buttonWidget(parent=self._subContainer,
                                                 position=(self._subWidth/2-thisButtonWidth/2,v-14),
                                                 size=(thisButtonWidth,60),
                                                 autoSelect=True,
                                                 label=R.benchmarksText,
                                                 textScale=1.0,
                                                 onActivateCall=self._onBenchmarkPress)

        bs.widget(edit=self._vrTestButton if self._vrTestButton is not None else self._netTestButton if self._netTestButton is not None else self._benchmarksButton,
                  upWidget=cb)
        
        #bs.widget(edit=showUserModsButton,downWidget=promoCodeButton)
        #bs.widget(edit=moddingGuideButton,upWidget=translationEditorButton)
        # for b in [showUserModsButton,moddingGuideButton,promoCodeButton]:
        #     bs.widget(edit=b,showBufferBottom=30)

        for w in self._subContainer.getChildren():
            bs.widget(edit=w,showBufferBottom=30,showBufferTop=20)
        #bs.widget(edit=promoCodeButton,upWidget=showUserModsButton)

        self._restoreState()
        
    def _onVRTestPress(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = VRTestingWindow(transition='inRight').getRootWidget()

    def _onNetTestPress(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = NetTestingWindow(transition='inRight').getRootWidget()

    def _onFriendPromoCodePress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        doAppInvitesPress()
        
    def _onPromoCodePress(self):

        # we have to be logged in for promo-codes to work..
        if bsInternal._getAccountState() != 'SIGNED_IN':
            # bs.playSound(bs.getSound('error'))
            # bs.screenMessage(bs.getResource('notSignedInErrorText'),color=(1,0,0))
            showSignInPrompt()
            return
        
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = PromoCodeWindow(originWidget=self._promoCodeButton).getRootWidget()

    def _onBenchmarkPress(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = DebugWindow(transition='inRight').getRootWidget()
        
    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._scrollWidget:
                sel = self._subContainer.getSelectedChild()
                if sel == self._vrTestButton: selName = 'VRTest'
                elif sel == self._netTestButton: selName = 'NetTest'
                elif sel == self._promoCodeButton: selName = 'PromoCode'
                # elif sel == self._friendPromoCodeButton: selName = 'FriendPromoCode'
                elif sel == self._benchmarksButton: selName = 'Benchmarks'
                elif sel == self._kickIdlePlayersCheckBox: selName = 'KickIdlePlayers'
                elif sel == self._alwaysUseInternalKeyboardCheckBox: selName = 'AlwaysUseInternalKeyboard'
                elif sel == self._kidFriendlyCheckBox: selName = 'KidFriendly'
                elif sel == self._languagePopup.getButtonWidget(): selName = 'Languages'
                elif sel == self._translationEditorButton: selName = 'TranslationEditor'
                elif sel == self._showUserModsButton: selName = 'ShowUserMods'
                elif sel == self._moddingGuideButton: selName = 'ModdingGuide'
                elif sel == self._enablePackageModsCheckBox: selName = 'PackageMods'
                else: raise Exception("unrecognized selection")
            elif sel == self._backButton: selName = 'Back'
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = {'selName':selName}
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]['selName']
            except Exception: selName = None
            if selName == 'Back':
                sel = self._backButton
                subSel = None
            else:
                bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)
                if selName == 'VRTest': sel = self._vrTestButton
                elif selName == 'NetTest': sel = self._netTestButton
                elif selName == 'PromoCode': sel = self._promoCodeButton
                #elif selName == 'FriendPromoCode': sel = self._friendPromoCodeButton
                elif selName == 'Benchmarks': sel = self._benchmarksButton
                elif selName == 'KickIdlePlayers': sel = self._kickIdlePlayersCheckBox
                elif selName == 'KidFriendly': sel = self._kidFriendlyCheckBox
                elif selName == 'AlwaysUseInternalKeyboard': sel = self._alwaysUseInternalKeyboardCheckBox
                elif selName == 'Languages': sel = self._languagePopup.getButtonWidget()
                elif selName == 'TranslationEditor': sel = self._translationEditorButton
                elif selName == 'ShowUserMods': sel = self._showUserModsButton
                elif selName == 'ModdingGuide': sel = self._moddingGuideButton
                elif selName == 'PackageMods': sel = self._enablePackageModsCheckBox
                else: sel = None
                if sel != None: bs.containerWidget(edit=self._subContainer,selectedChild=sel,visibleChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)
    
    def _onMenuOpen(self):
        self._menuOpen = True

    def _onMenuClose(self):
        self._menuOpen = False

    def _onMenuChoice(self,choice):
        if choice == 'Auto': bsUtils._setLanguage(None)
        else:
            try:
                # attempt to reload the language module first.. (this makes iterating on a language easier)
                langModule = __import__('bsLanguage'+choice)
                reload(langModule)
            except Exception:
                bs.printException('error on language switch reload for lang \''+choice+'\':')
            bsUtils._setLanguage(choice)
        self._saveState()
        bs.realTimer(100,bs.WeakCall(self._rebuild))

    def _completedLangsCB(self,results):
        if results is not None:
            self._completeLangsList = results['langs']
            self._completeLangsError = False
        else:
            self._completeLangsList = None
            self._completeLangsError = True
        bs.realTimer(1,bs.WeakCall(self._updateLangStatus))
            

    def _doBack(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = SettingsWindow(transition='inLeft').getRootWidget()

class SettingsWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):

        bsInternal._setAnalyticsScreen('Settings Window')
        
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None

        width = 750 if gSmallUI else 580
        height = 435

        buttonHeight = 42

        R = bs.getResource('settingsWindow')

        topExtra = 20 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(width,height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=1.75 if gSmallUI else 1.35 if gMedUI else 1.0,
                                              stackOffset=(0,-8) if gSmallUI else (0,0))
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(40,height-55),size=(130,60),scale=0.8,textScale=1.2,
                                               label=bs.getResource('backText'),buttonType='back',onActivateCall=self._doBack)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(0,height-44),size=(width,25),
                          text=R.titleText,color=gTitleColor,hAlign="center",vAlign="center",maxWidth=130)

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(103,height-45))
        
        
        # remind existing players that we moved this for about 10 launches...
        bsConfig = bs.getConfig()
        lc14146 = bsConfig.get('lc14146',0)
        lcSince = bsConfig.get('launchCount',0) - lc14146
        showAccountsMoved = True if lc14146 > 1 and lcSince < 10 else False
        if showAccountsMoved:
            t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,50 if gSmallUI else 35),size=(0,0),
                              text=R.playerProfilesMovedText,color=gInfoTextColor,flatness=1.0, scale=0.5,
                              hAlign="center",vAlign="center",maxWidth=width*0.8)
        
        v = height - 80
        v -= 140 if gSmallUI and showAccountsMoved else 145

        #bw = 215 if gSmallUI else 180
        bw = 280 if gSmallUI else 230
        bh = 160 if gSmallUI and showAccountsMoved else 170
        #xOffs = 60 if gSmallUI else 36
        xOffs = (105 if gSmallUI else 72) - bw # now unused
        xOffs2 = xOffs+bw-7
        xOffs3 = xOffs+2*(bw-7)
        #xOffs4 = xOffs+0.5*(bw-7)
        xOffs4 = xOffs2
        #xOffs5 = xOffs+1.5*(bw-7)
        xOffs5 = xOffs3
        def _bTitle(x,y,button,text):
            bs.textWidget(parent=self._rootWidget,text=text,position=(x+bw*0.47,y+bh*0.22),
                          maxWidth=bw*0.7,size=(0,0),hAlign='center',vAlign='center',drawController=button,
                          color=(0.7,0.9,0.7,1.0))

        # acb = self._accountButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(xOffs,v),size=(bw,bh),buttonType='square',
        #                                                label='',onActivateCall=self._doAccount)
        # _bTitle(xOffs,v,acb,R.accountText)
        # iw = ih = 110
        # bs.imageWidget(parent=self._rootWidget,position=(xOffs+bw*0.49-iw*0.5,v+45),size=(iw,ih),
        #                            texture=bs.getTexture('accountIcon'),drawController=acb)
            
        # pb = self._profilesButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(xOffs,v),size=(bw,bh),buttonType='square',
        #                                            label='',onActivateCall=self._doProfiles)
        # _bTitle(xOffs,v,pb,R.playerProfilesText)
        # iw = ih = 100
        # bs.imageWidget(parent=self._rootWidget,position=(xOffs+bw*0.49-iw*0.5,v+43),size=(iw,ih),
        #                            texture=bs.getTexture('cuteSpaz'),drawController=pb)

        cb = self._controllersButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(xOffs2,v),size=(bw,bh),buttonType='square',
                                                      label='',onActivateCall=self._doControllers)
        _bTitle(xOffs2,v,cb,R.controllersText)
        iw = ih = 130
        bs.imageWidget(parent=self._rootWidget,position=(xOffs2+bw*0.49-iw*0.5,v+35),size=(iw,ih),
                                   texture=bs.getTexture('controllerIcon'),drawController=cb)

        gb = self._graphicsButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(xOffs3,v),size=(bw,bh),buttonType='square',
                                                   label='',onActivateCall=self._doGraphics)
        _bTitle(xOffs3,v,gb,R.graphicsText)
        iw = ih = 110
        bs.imageWidget(parent=self._rootWidget,position=(xOffs3+bw*0.49-iw*0.5,v+42),size=(iw,ih),
                                   texture=bs.getTexture('graphicsIcon'),drawController=gb)
        
        v -= (bh-5)


        ab = self._audioButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(xOffs4,v),size=(bw,bh),buttonType='square',
                                                label='',onActivateCall=self._doAudio)
        _bTitle(xOffs4,v,ab,R.audioText)
        iw = ih = 120
        bs.imageWidget(parent=self._rootWidget,position=(xOffs4+bw*0.49-iw*0.5+5,v+35),size=(iw,ih),
                       color=(1,1,0),
                       texture=bs.getTexture('audioIcon'),drawController=ab)


        avb = self._advancedButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(xOffs5,v),size=(bw,bh),buttonType='square',
                                                         label='',onActivateCall=self._doAdvanced)
        _bTitle(xOffs5,v,avb,R.advancedText)
        iw = ih = 120
        bs.imageWidget(parent=self._rootWidget,position=(xOffs5+bw*0.49-iw*0.5+5,v+35),size=(iw,ih),
                       color=(0.8,0.95,1),
                       texture=bs.getTexture('advancedIcon'),drawController=avb)


        # self._profilesButton = b = bs.buttonWidget(parent=self._rootWidget,position=(53,v),size=(width-110,buttonHeight),
        #                                            label=R.playerProfilesText,onActivateCall=self._doProfiles)
        # v -= spacing * 1.6
        # self._controllersButton = b = bs.buttonWidget(parent=self._rootWidget,position=(61,v),size=(width-110,buttonHeight),
        #                                               label=R.controllersText,onActivateCall=self._doControllers)
        # v -= spacing * 1.6

        # self._graphicsButton = b = bs.buttonWidget(parent=self._rootWidget,position=(51,v),size=(width-110,buttonHeight),
        #                                            label=R.graphicsText,onActivateCall=self._doGraphics)
        # v -= spacing * 1.6
        # self._audioButton = b = bs.buttonWidget(parent=self._rootWidget,position=(57,v),size=(width-110,buttonHeight),
        #                                         label=R.audioText,onActivateCall=self._doAudio)
        # v -= spacing * 1.4
        # avb = self._advancedButton = b = bs.buttonWidget(parent=self._rootWidget,position=(59,v),size=(width-110,buttonHeight),
        #                                                  label=R.advancedText,onActivateCall=self._doAdvanced,
        #                                                  color=(0.55,0.5,0.6),
        #                                                  textColor=(0.65,0.6,0.7),
        # )

        # bs.buttonWidget(edit=acb,downWidget=gb)
        # bs.buttonWidget(edit=pb,downWidget=ab,upWidget=self._backButton)
        # bs.buttonWidget(edit=cb,downWidget=avb,upWidget=self._backButton)
        # bs.buttonWidget(edit=gb,upWidget=acb)
        # bs.buttonWidget(edit=ab,upWidget=pb)
        # bs.buttonWidget(edit=avb,upWidget=cb)
        # bs.buttonWidget(edit=cb,downWidget=ab)
        # bs.buttonWidget(edit=gb,downWidget=avb,upWidget=pb)
        # bs.buttonWidget(edit=ab,downWidget=avb,upWidget=cb)
        # bs.buttonWidget(edit=avb,upWidget=gb)

        # if 0:
        #     v -= spacing * 1.57
        #     configCheckBox(parent=self._rootWidget,position=(60,v),size=(width-100,30),name="Show Player Names",displayName=R.showPlayerNamesText,scale=0.9)
        #     v -= spacing * 1.27
        #     configCheckBox(parent=self._rootWidget,position=(60,v),size=(width-100,30),name="Kick Idle Players",displayName=R.kickIdlePlayersText,scale=0.9)
        #     v -= spacing * 0.63

        #     thisButtonWidth = 140
        #     b = bs.buttonWidget(parent=self._rootWidget,position=(width/2-thisButtonWidth/2,v-14),
        #                         color=(0.45,0.4,0.5),
        #                         size=(thisButtonWidth,22),
        #                         label=R.enterPromoCodeText,
        #                         textColor=(0.55,0.5,0.6),
        #                         textScale=0.7,
        #                         onActivateCall=PromoCodeWindow)


        self._restoreState()

        # re-select previous if applicable
        # selected = None
        # try:
        #     global gSettingsSelection
        #     try: selName = gSettingsSelection
        #     except Exception: selName = ''
        #     if selName == 'Account': selected = self._accountButton
        #     elif selName == 'Profiles': selected = self._profilesButton
        #     elif selName == 'Controllers': selected = self._controllersButton
        #     elif selName == 'Graphics': selected = self._graphicsButton
        #     elif selName == 'Audio': selected = self._audioButton
        #     elif selName == 'Advanced': selected = self._advancedButton
        # except Exception,ex:
        #     print 'Exception restoring settings UI state:',ex

        # if selected is not None: bs.containerWidget(edit=self._rootWidget,selectedChild=selected)
        # else: bs.containerWidget(edit=self._rootWidget,selectedChild=self._accountButton)

    def _doBack(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()

    # def _doAccount(self):
    #     self._saveState()
    #     bs.containerWidget(edit=self._rootWidget,transition='outLeft')
    #     uiGlobals['mainMenuWindow'] = AccountWindow().getRootWidget()

    # def _doProfiles(self):
    #     self._saveState()
    #     bs.containerWidget(edit=self._rootWidget,transition='outLeft')
    #     uiGlobals['mainMenuWindow'] = PlayerProfilesWindow().getRootWidget()

    def _doControllers(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ControllersWindow(originWidget=self._controllersButton).getRootWidget()

    def _doGraphics(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = GraphicsWindow(originWidget=self._graphicsButton).getRootWidget()

    def _doAudio(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = ConfigAudioWindow(originWidget=self._audioButton).getRootWidget()

    def _doAdvanced(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = AdvancedSettingsWindow(originWidget=self._advancedButton).getRootWidget()

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            #if sel == self._accountButton: selName = 'Account'
            #if sel == self._profilesButton: selName = 'Profiles'
            if sel == self._controllersButton: selName = 'Controllers'
            elif sel == self._graphicsButton: selName = 'Graphics'
            elif sel == self._audioButton: selName = 'Audio'
            elif sel == self._advancedButton: selName = 'Advanced'
            elif sel == self._backButton: selName = 'Back'
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = {'selName':selName}
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]['selName']
            except Exception: selName = None
            #if selName == 'Account': sel = self._accountButton
            # elif selName == 'Profiles': sel = self._profilesButton
            if selName == 'Controllers': sel = self._controllersButton
            elif selName == 'Graphics': sel = self._graphicsButton
            elif selName == 'Audio': sel = self._audioButton
            elif selName == 'Advanced': sel = self._advancedButton
            elif selName == 'Back': sel = self._backButton
            else: sel = self._controllersButton
            #else: sel = self._profilesButton
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)

class SelectMapWindow(Window):

    def __init__(self,gameClass,sessionType,config,editInfo,completionCall,transition='inRight'):

        self._gameClass = gameClass
        self._sessionType = sessionType
        self._config = config
        self._completionCall = completionCall
        self._editInfo = editInfo

        try: self._previousMap = bsMap.getFilteredMapName(config['map'])
        except Exception: self._previousMap = ''

        width = 615
        height = 400 if gSmallUI else 480 if gMedUI else 600
        spacing = 40

        topExtra = 20 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(width,height+topExtra),transition=transition,
                                              scale=2.17 if gSmallUI else 1.3 if gMedUI else 1.0,
                                              stackOffset=(0,-27) if gSmallUI else (0,0))

        self._cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(38,height-67),size=(140,50),scale=0.9,textScale=1.0,
                                                 autoSelect=True,label=bs.getResource('cancelText'),onActivateCall=self._cancel)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        t = bs.textWidget(parent=self._rootWidget,position=(width*0.5,height-46),size=(0,0),maxWidth=260,scale=1.1,
                          text=bs.getResource('mapSelectTitleText').replace('${GAME}',self._gameClass.getNameLocalized()),color=gTitleColor,
        # t = bs.textWidget(parent=self._rootWidget,position=(0,height-49),size=(width,25),text=gameClass.getName()+" Maps",color=gTitleColor,
                          hAlign="center",vAlign="center")
        v = height - 70
        self._scrollWidth = width-80
        self._scrollHeight = height - 140
        
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(40,v-self._scrollHeight),
                                             size=(self._scrollWidth,self._scrollHeight))
        bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)

        # if 0:
        #     mapList = self._gameClass.getSupportedMaps(self._sessionType)

        #     c = bs.columnWidget(parent=self._scrollWidget,leftBorder=10,topBorder=2,bottomBorder=2)
        #     v -= self._scrollHeight
        #     modelOpaque = bs.getModel('levelSelectButtonOpaque')
        #     modelTransparent = bs.getModel('levelSelectButtonTransparent')
        #     mapListSorted = list(mapList)
        #     mapListSorted.sort()
        #     maskTex = bs.getTexture('mapPreviewMask')
        #     for m in mapListSorted:
        #         mapTexName = bsMap.getMapClass(m).getPreviewTextureName()
        #         if mapTexName is not None:
        #             mapTex = bs.getTexture(mapTexName)
        #         else:
        #             print 'Error: no map preview texture for map:',m
        #             mapTex = None
        #         sc = 0.99
        #         b = bs.buttonWidget(parent=c,size=(500.0*sc,125.0*sc),
        #                             label=bsMap.getLocalizedMapName(m),
        #                             onActivateCall=bs.WeakCall(self._selectWithDelay,m),
        #                             texture=mapTex,
        #                             color=(0.5,0.5,0.5),
        #                             modelOpaque=modelOpaque,
        #                             modelTransparent=modelTransparent,
        #                             maskTexture=maskTex)
        #         if m == self._previousMap:
        #             bs.columnWidget(edit=c,selectedChild=b,visibleChild=b)
        self._subContainer = None
        self._refresh()

    def _refresh(self,selectGetMoreMapsButton=False):

        # kill old
        if self._subContainer is not None:
            self._subContainer.delete()

        modelOpaque = bs.getModel('levelSelectButtonOpaque')
        modelTransparent = bs.getModel('levelSelectButtonTransparent')


        self._maps = []
        mapList = self._gameClass.getSupportedMaps(self._sessionType)
        mapListSorted = list(mapList)
        mapListSorted.sort()
        
        # unOwnedMaps = set()
        # for mapSection in _getStoreLayout()['maps']:
        #     for m in mapSection['items']:
        #         if not bsInternal._getPurchased(m['name']):
        #             unOwnedMaps.add(m['mapType'].name)
        unOwnedMaps = bsMap._getUnOwnedMaps()
        
        for m in mapListSorted:
            # disallow ones we don't own
            if m in unOwnedMaps: continue
            mapTexName = bsMap.getMapClass(m).getPreviewTextureName()
            if mapTexName is not None:
                try:
                    mapTex = bs.getTexture(mapTexName)
                    self._maps.append((m,mapTex))
                except Exception:
                    print 'invalid map preview texture: "'+mapTexName+'"'
            else: print 'Error: no map preview texture for map:',m

        #print 'FIN MAP LIST',self._maps
        
        # make a list of spaz icons
        # self._spazzes = bsSpaz.getAppearances()
        # self._spazzes.sort()
        # self._iconTextures = [bs.getTexture(bsSpaz.appearances[s].iconTexture) for s in self._spazzes]
        # self._iconTintTextures = [bs.getTexture(bsSpaz.appearances[s].iconMaskTexture) for s in self._spazzes]
        # maskTexture=bs.getTexture('characterIconMask')
        
        count = len(self._maps)
        
        columns = 2
        rows = int(math.ceil(float(count)/columns))
        
        buttonWidth = 220
        buttonHeight = buttonWidth * 0.5
        buttonBufferH = 16
        buttonBufferV = 19

        self._subWidth = self._scrollWidth*0.95
        self._subHeight = 5+rows*(buttonHeight+2*buttonBufferV) + 100
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),
                                                background=False)
        index = 0
        maskTexture=bs.getTexture('mapPreviewMask')
        hOffs = 130 if len(self._maps) == 1 else 0
        for y in range(rows):
            for x in range(columns):
                pos = (x*(buttonWidth+2*buttonBufferH)+buttonBufferH+hOffs,
                       self._subHeight - (y+1)*(buttonHeight+2*buttonBufferV)+12)
                b = bs.buttonWidget(parent=self._subContainer,buttonType='square',
                                    size=(buttonWidth,buttonHeight),
                                    autoSelect=True,
                                    texture=self._maps[index][1],
                                    #tintTexture=self._iconTintTextures[index],
                                    maskTexture=maskTexture,
                                    modelOpaque=modelOpaque,
                                    modelTransparent=modelTransparent,
                                    label='',
                                    color=(1,1,1),
                                    #tintColor=tintColor,
                                    #tint2Color=tint2Color,
                                    onActivateCall=bs.Call(self._selectWithDelay,self._maps[index][0]),
                                    position=pos)
                if x == 0: bs.widget(edit=b,leftWidget=self._cancelButton)
                if y == 0: bs.widget(edit=b,upWidget=self._cancelButton)
                bs.widget(edit=b,showBufferTop=60,showBufferBottom=60)
                if self._maps[index][0] == self._previousMap:
                    bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)
                # if self._spazzes[index] == selectedCharacter:
                #     bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)
                #name = bs.translate('characterNames',self._spazzes[index])
                name = bsMap.getLocalizedMapName(self._maps[index][0])
                bs.textWidget(parent=self._subContainer,text=name,position=(pos[0]+buttonWidth*0.5,pos[1]-12),
                              size=(0,0),scale=0.5,maxWidth=buttonWidth,
                              drawController=b,hAlign='center',vAlign='center',color=(0.8,0.8,0.8,0.8))
                index += 1
                
                if index >= count: break
            if index >= count: break
        self._getMoreMapsButton = b = bs.buttonWidget(parent=self._subContainer,
                                                      size=(self._subWidth*0.8,60),position=(self._subWidth*0.1,30),
                                                      label=bs.getResource('mapSelectGetMoreMapsText'),
                                                      onActivateCall=self._onStorePress,
                                                      color=(0.6,0.53,0.63),
                                                      textColor=(0.75,0.7,0.8),
                                                      autoSelect=True)
        bs.widget(edit=b,showBufferTop=30,showBufferBottom=30)
        if selectGetMoreMapsButton:
            bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)


    def _onStorePress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        StoreWindow(modal=True,showTab='maps',onCloseCall=self._onStoreClose,originWidget=self._getMoreMapsButton)

    def _onStoreClose(self):
        self._refresh(selectGetMoreMapsButton=True)
        
    def _select(self,mapName):
        self._config['settings']['map'] = mapName
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = GameSettingsSelectWindow(self._gameClass,self._sessionType,self._config,
                                                               self._completionCall,
                                                               defaultSelection='map',
                                                               transition='inLeft',
                                                               editInfo=self._editInfo).getRootWidget()
    def _selectWithDelay(self,mapName):
        bsInternal._lockAllInput()
        bs.realTimer(100,bsInternal._unlockAllInput)
        bs.realTimer(100,bs.WeakCall(self._select,mapName))

    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = GameSettingsSelectWindow(self._gameClass,self._sessionType,self._config,
                                                               self._completionCall,
                                                               defaultSelection='map',
                                                               transition='inLeft',
                                                               editInfo=self._editInfo).getRootWidget()


class GameSettingsSelectWindow(Window):

    def __init__(self,gameClass,sessionType,config,completionCall,defaultSelection=None,transition='inRight',editInfo=None):
        self._gameClass = gameClass
        self._sessionType = sessionType

        # if we're within an editing session we get passed editInfo (returning from map selection window, etc)
        if editInfo is not None:
            self._editInfo = editInfo
        # ..otherwise determine whether we're adding or editing a game based on whether an existing config was passed to us
        else:
            if config is None: self._editInfo = {'editType':'add'}
            else: self._editInfo = {'editType':'edit'}
        
        #self._editInfo = editInfo
        self._R = bs.getResource('gameSettingsWindow')

        #validMapsIncludingUnOwned = gameClass.getSupportedMaps(sessionType,includeUnOwned=True)
        validMaps = gameClass.getSupportedMaps(sessionType)
        if len(validMaps) == 0:
            bs.screenMessage(bs.getResource('noValidMapsErrorText'))
            raise Exception("No valid maps")

        self._settingsDefs = gameClass.getSettings(sessionType)
        self._completionCall = completionCall

        # to start with, pick a random map out of the ones we own
        unOwnedMaps = bsMap._getUnOwnedMaps()
        validMapsOwned = [m for m in validMaps if m not in unOwnedMaps]
        if validMapsOwned: self._map = validMaps[random.randrange(len(validMapsOwned))]
        # hmmm.. we own none of these maps.. just pick a random un-owned one i guess.. should this ever happen?..
        else: self._map = validMaps[random.randrange(len(validMaps))]

        isAdd = (self._editInfo['editType'] == 'add')
        
        # if there's a valid map name in the existing config, use that.
        try:
            if config is not None and 'settings' in config and 'map' in config['settings']:
                filteredMapName = bsMap.getFilteredMapName(config['settings']['map'])
                if filteredMapName in validMaps: self._map = filteredMapName
        except Exception:
            bs.printException('exception getting map for editor')

        if config is not None and 'settings' in config: self._settings = config['settings']
        else: self._settings = {}

        self._choiceSelections = {}

        width = 620
        height = 365 if gSmallUI else 460 if gMedUI else 550
        spacing = 52
        # yExtra = 0 if gSmallUI else 15
        # yExtra2 = 0 if gSmallUI else 21
        yExtra =15
        yExtra2 = 21

        mapTexName = bsMap.getMapClass(self._map).getPreviewTextureName()
        if mapTexName is None:
            raise Exception("no map preview tex found for"+self._map)
        mapTex = bs.getTexture(mapTexName)

        topExtra = 20 if gSmallUI else 0
        self._rootWidget =  bs.containerWidget(size=(width,height+topExtra),transition=transition,
                                               scale=2.19 if gSmallUI else 1.35 if gMedUI else 1.0,
                                               stackOffset=(0,-17) if gSmallUI else (0,0))

        # if isAdd:
        b = bs.buttonWidget(parent=self._rootWidget,
                            position=(45,height-82+yExtra2),
                            size=(180,70) if isAdd else (180,65),
                            # position=(40,height-82+yExtra2) if isAdd else (40,height-79+yExtra2),
                            # size=(140,65) if isAdd else (140,60),
                            label=bs.getResource('backText') if isAdd else bs.getResource('cancelText'),
                            buttonType='back' if isAdd else None,
                            scale=0.75,textScale=1.3,
                            onActivateCall=bs.Call(self._cancel))
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        addButton = b = bs.buttonWidget(parent=self._rootWidget,
                                        position=(width-193,height-82+yExtra2),
                                        size=(200,65),
                                        # position=(width-178,height-79+yExtra2) if isAdd else (width-150,height-79+yExtra2),
                                        # size=(180,60) if isAdd else (140,60),
                                        scale=0.75,
                                        textScale=1.3,
                                        label=self._R.addGameText if isAdd else bs.getResource('doneText'))
        t = bs.textWidget(parent=self._rootWidget,position=(-8,height-70+yExtra2),size=(width,25),
                          text=gameClass.getNameLocalized(),
                          color=gTitleColor,maxWidth=235,
                          scale=1.1,hAlign="center",vAlign="center")

        mapHeight = 100

        scrollHeight = mapHeight + 10 # map select and margin
        # calc our total height we'll need
        for settingName,setting in self._settingsDefs:
            scrollHeight += spacing

        scrollWidth = width-86
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(44,35+yExtra),size=(scrollWidth,height-116),highlight=False)
        self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,size=(scrollWidth,scrollHeight),background=False)

        # so selection loops through everything and doesn't get stuck in sub-containers
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=c,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)

        v = scrollHeight - 5
        h = -40

        # keep track of all the selectable widgets we make so we can wire them up conveniently
        widgetColumn = []
        
        # map select button
        t = bs.textWidget(parent=self._subContainer,position=(h+49,v-63),size=(100,30),maxWidth=110,
                          text=bs.getResource('mapText'),hAlign="left",color=(0.8,0.8,0.8,1.0),vAlign="center")

        mapName = bsMap.getLocalizedMapName(self._map)

        b = bs.imageWidget(parent=self._subContainer,size=(256*0.7,125*0.7),
                           position=(h+261-128+128.0*0.56,v-90),
                           texture=mapTex,
                           modelOpaque=bs.getModel('levelSelectButtonOpaque'),
                           modelTransparent=bs.getModel('levelSelectButtonTransparent'),
                           maskTexture=bs.getTexture('mapPreviewMask'))
        mapButton = b = bs.buttonWidget(parent=self._subContainer,size=(140,60),
                                        position=(h+448,v-72),
                                        onActivateCall=bs.Call(self._selectMap),
                                        scale=0.7,
                                        label=bs.getResource('mapSelectText'))
        widgetColumn.append([b])
        
        mapNameText = bs.textWidget(parent=self._subContainer,position=(h+363-123,v-114),size=(100,30),flatness=1.0,shadow=1.0,
                                    scale=0.55,maxWidth=256*0.7*0.8,
                                    text=bsMap.getLocalizedMapName(self._map),hAlign="center",
                                    color=(0.6,1.0,0.6,1.0),vAlign="center")
        v -= mapHeight

        for settingName,setting in self._settingsDefs:
            value = setting['default']
            valueType = type(value)

            # now if there's an existing value for it in the config, override with that
            try: value = valueType(config['settings'][settingName])
            except Exception: pass

            # shove the starting value in there to start..
            self._settings[settingName] = value

            nameTranslated = self._getLocalizedSettingName(settingName)

            mw1 = 280
            mw2 = 70
            
            # handle types with choices specially:
            if 'choices' in setting:

                for choice in setting['choices']:
                    if len(choice) != 2: raise Exception("Expected 2-member tuples for 'choices'; got: "+repr(choice))
                    if type(choice[0]) not in (str,unicode): raise Exception("First value for choice tuple must be a str; got: "+repr(choice))
                    if type(choice[1]) is not valueType: raise Exception("Choice type does not match default value; choice:"+repr(choice)+"; setting:"+repr(setting))
                if valueType not in (int,float): raise Exception("Choice type setting must have int or float default; got: "+repr(setting))

                # start at the choice corresponding to the default if possible
                self._choiceSelections[settingName] = 0
                found = False
                for index,choice in enumerate(setting['choices']):
                    if choice[1] == value:
                        self._choiceSelections[settingName] = index
                        break;

                v -= spacing
                t = bs.textWidget(parent=self._subContainer,position=(h+50,v),size=(100,30),maxWidth=mw1,
                                  text=nameTranslated,hAlign="left",color=(0.8,0.8,0.8,1.0),vAlign="center")
                t = bs.textWidget(parent=self._subContainer,position=(h+509-95,v),size=(0,28),
                                  text=self._getLocalizedSettingName(setting['choices'][self._choiceSelections[settingName]][0]),editable=False,
                                  color=(0.6,1.0,0.6,1.0),maxWidth=mw2,
                                  hAlign="right",vAlign="center",padding=2)
                b1 = bs.buttonWidget(parent=self._subContainer,position=(h+509-50-1,v),size=(28,28),label="<",
                                    onActivateCall=bs.Call(self._choiceInc,settingName,t,setting,-1),repeat=True)
                b2 = bs.buttonWidget(parent=self._subContainer,position=(h+509+5,v),size=(28,28),label=">",
                                    onActivateCall=bs.Call(self._choiceInc,settingName,t,setting,1),repeat=True)
                widgetColumn.append([b1,b2])

            elif valueType in [int,float]:
                v -= spacing
                try: minValue = setting['minValue']
                except Exception: minValue = 0
                try: maxValue = setting['maxValue']
                except Exception: maxValue = 9999
                try: increment = setting['increment']
                except Exception: increment = 1
                t = bs.textWidget(parent=self._subContainer,position=(h+50,v),size=(100,30),
                                  text=nameTranslated,hAlign="left",color=(0.8,0.8,0.8,1.0),vAlign="center",maxWidth=mw1)
                t = bs.textWidget(parent=self._subContainer,position=(h+509-95,v),size=(0,28),
                                  text=str(value),editable=False,
                                  color=(0.6,1.0,0.6,1.0),maxWidth=mw2,
                                  hAlign="right",vAlign="center",padding=2)
                b1 = bs.buttonWidget(parent=self._subContainer,position=(h+509-50-1,v),size=(28,28),label="-",
                                    onActivateCall=bs.Call(self._inc,t,minValue,maxValue,-increment,valueType,settingName),repeat=True)
                b2 = bs.buttonWidget(parent=self._subContainer,position=(h+509+5,v),size=(28,28),label="+",
                                    onActivateCall=bs.Call(self._inc,t,minValue,maxValue,increment,valueType,settingName),repeat=True)
                widgetColumn.append([b1,b2])
                
            elif valueType == bool:
                v -= spacing
                t = bs.textWidget(parent=self._subContainer,position=(h+50,v),size=(100,30),
                                  text=nameTranslated,hAlign="left",color=(0.8,0.8,0.8,1.0),vAlign="center",maxWidth=mw1)
                t = bs.textWidget(parent=self._subContainer,position=(h+509-95,v),size=(0,28),
                                  text=bs.getResource('onText') if value else bs.getResource('offText'),editable=False,
                                  color=(0.6,1.0,0.6,1.0),maxWidth=mw2,
                                  hAlign="right",vAlign="center",padding=2)
                c = bs.checkBoxWidget(parent=self._subContainer,text='',position=(h+505-50-5,v-2),size=(200,30),
                                      textColor=(0.8,0.8,0.8),
                                      value=value,onValueChangeCall=bs.Call(self._checkValueChange,settingName,t))
                widgetColumn.append([c])
                
            else: raise Exception()

            
        # ok now wire up the column
        try:
            prevWidgets = None
            for c in widgetColumn:
                if prevWidgets is not None:
                    # wire our rightmost to their rightmost
                    bs.widget(edit=prevWidgets[-1],downWidget=c[-1])
                    bs.widget(c[-1],upWidget=prevWidgets[-1])
                    # wire our leftmost to their leftmost
                    bs.widget(edit=prevWidgets[0],downWidget=c[0])
                    bs.widget(c[0],upWidget=prevWidgets[0])
                prevWidgets = c
        except Exception:
            bs.printException('error wiring up game-settings-select widget column')

        bs.buttonWidget(edit=addButton,onActivateCall=bs.Call(self._add))
        bs.containerWidget(edit=self._rootWidget,selectedChild=addButton,startButton=addButton)

        if defaultSelection == 'map':
            bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)
            bs.containerWidget(edit=self._subContainer,selectedChild=mapButton)

    def _getLocalizedSettingName(self,name):
        # try: nameTranslated = bs.getResource('translations.settingNames')[name]
        # except Exception: nameTranslated = None
        # if nameTranslated is None: nameTranslated = name
        nameTranslated = bs.translate('settingNames',name)
        return nameTranslated
        
    def _selectMap(self):
        # replace ourself with the map-select UI
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = SelectMapWindow(self._gameClass,self._sessionType,copy.deepcopy(self._getConfig()),
                                                  self._editInfo,self._completionCall).getRootWidget()
    def _choiceInc(self,settingName,widget,setting,increment):
        choices = setting['choices']
        if increment > 0: self._choiceSelections[settingName] = min(len(choices)-1,self._choiceSelections[settingName]+1)
        else: self._choiceSelections[settingName] = max(0,self._choiceSelections[settingName]-1)
        bs.textWidget(edit=widget,text=self._getLocalizedSettingName(choices[self._choiceSelections[settingName]][0]))
        self._settings[settingName] = choices[self._choiceSelections[settingName]][1]

    def _cancel(self):
        self._completionCall(None)

    def _checkValueChange(self,settingName,widget,value):
        bs.textWidget(edit=widget,text=bs.getResource('onText') if value else bs.getResource('offText'))
        self._settings[settingName] = value

    def _getConfig(self):
        return {'map':self._map,'settings':self._settings}

    def _add(self):
        self._completionCall(copy.deepcopy(self._getConfig()))

    def _inc(self,ctrl,minVal,maxVal,increment,settingType,settingName):
        if settingType == float: val = float(bs.textWidget(query=ctrl))
        else: val = int(bs.textWidget(query=ctrl))
        val += increment
        val = max(minVal,min(val,maxVal))
        if settingType == float: bs.textWidget(edit=ctrl,text=str(round(val,2)))
        elif settingType == int: bs.textWidget(edit=ctrl,text=str(int(val)))
        else: raise Exception('invalid vartype: '+str(vartype))
        self._settings[settingName] = val


class AddGameWindow(Window):

        
    def __init__(self,editSession,transition='inRight'):
        self._editSession = editSession
        self._R = R = bs.getResource('addGameWindow')
        self._width = 650
        self._height = 346 if gSmallUI else 380 if gMedUI else 440
        topExtra = 30 if gSmallUI else 20

        self._scrollWidth = 210
        
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scale=2.17 if gSmallUI else 1.5 if gMedUI else 1.0,
                                              stackOffset=(0,1) if gSmallUI else (0,0))
        
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(58,self._height-53),
                                         size=(165,70),scale=0.75,textScale=1.2,label=bs.getResource('backText'),
                                         autoSelect=True,
                                         buttonType='back',onActivateCall=self._back)
        self._selectButton = selectButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-172,self._height-50),
                                           autoSelect=True,size=(160,60),scale=0.75,textScale=1.2,label=bs.getResource('selectText'),onActivateCall=self._add)
        bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-28),size=(0,0),scale=1.0,
                      text=R.titleText,hAlign='center',color=gTitleColor,maxWidth=250,
                      vAlign='center')
        v = self._height - 64


        self._selectedTitleText = bs.textWidget(parent=self._rootWidget,position=(self._scrollWidth+50+30,v-15),size=(0,0),
                                                scale=1.0,color=(0.7,1.0,0.7,1.0),maxWidth=self._width-self._scrollWidth-150,
                                                hAlign='left',vAlign='center')
        v -= 30

        self._selectedDescriptionText = bs.textWidget(parent=self._rootWidget,position=(self._scrollWidth+50+30,v),size=(0,0),
                                                      scale=0.7,color=(0.5,0.8,0.5,1.0),maxWidth=self._width-self._scrollWidth-150,
                                                      hAlign='left')

        #scrollHeight = 173 if gSmallUI else 220
        scrollHeight = self._height-100

        v = self._height - 60
        # v -= 95
        # v -= 94
        # v -= 75
        # if gSmallUI: v += 50


        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(61,v-scrollHeight),size=(self._scrollWidth,scrollHeight),highlight=False)
        bs.widget(edit=self._scrollWidget,upWidget=self._backButton,leftWidget=self._backButton,rightWidget=selectButton)
        self._column = None
        
        v -= 35
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._backButton,startButton=selectButton)
        self._selectedGameType = None

        bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)

        self._refresh()
        

    def _refresh(self,selectGetMoreGamesButton=False):

        if self._column is not None:
            self._column.delete()
        # for c in self._column.getChildren():
        #     c.delete()

        self._column = bs.columnWidget(parent=self._scrollWidget)
        gameTypes = [gt for gt in bsUtils.getGameTypes() if gt.supportsSessionType(self._editSession._sessionType)]
        # sort in this language
        gameTypes.sort(key=lambda g:g.getNameLocalized())
            
        for i,gameType in enumerate(gameTypes):
            t = bs.textWidget(parent=self._column,position=(0,0),size=(self._width-88,24),text=gameType.getNameLocalized(),
                              hAlign="left",vAlign="center",
                              color=(0.8,0.8,0.8,1.0),
                              maxWidth=self._scrollWidth*0.8,
                              onSelectCall=bs.Call(self._setSelectedGameType,gameType),
                              alwaysHighlight=True,
                              selectable=True,onActivateCall=bs.Call(bs.realTimer,100,self._selectButton.activate))
            if i == 0: bs.widget(edit=t,upWidget=self._backButton)
            #bs.containerWidget(edit=self._column,selectedChild=t,visibleChild=t)
            
        self._getMoreGamesButton = bs.buttonWidget(parent=self._column,autoSelect=True,
                                                   label=self._R.getMoreGamesText,
                                                   color=(0.54,0.52,0.67),
                                                   textColor=(0.7,0.65,0.7),
                                                   onActivateCall=self._onGetMoreGamesPress,
                                                   size=(178,50))
        if selectGetMoreGamesButton:
            bs.containerWidget(edit=self._column,selectedChild=self._getMoreGamesButton,
                               visibleChild=self._getMoreGamesButton)
        #ifbs.containerWidget(edit=col,visibleChild=
                                                   #position=(55,v-scrollHeight-16))
            
        #bs.widget(edit=t,downWidget=self._getMoreGamesButton) # last game type goes to this..
        
    def _onGetMoreGamesPress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        StoreWindow(modal=True,showTab='minigames',onCloseCall=self._onStoreClose,originWidget=self._getMoreGamesButton)

    def _onStoreClose(self):
        self._refresh(selectGetMoreGamesButton=True)
        
    def _add(self):
        bsInternal._lockAllInput() # make sure no more commands happen
        bs.realTimer(100,bsInternal._unlockAllInput)
        self._editSession._addGameTypeSelected(self._selectedGameType)

    # def _addDelayed(self):
    #     #self._selectButton.activate()
    #     #bs.playSound(bs.getSound('swish'))
    #     bs.realTimer(100,self._selectButton.activate)

    def _setSelectedGameType(self,gameType):
        self._selectedGameType = gameType
        bs.textWidget(edit=self._selectedTitleText,text=gameType.getNameLocalized())
        bs.textWidget(edit=self._selectedDescriptionText,text=gameType.getDescriptionLocalized(self._editSession.getSessionType()))

    def _back(self):
        self._editSession._addGameCancelled()


class EditPlaylistWindow(Window):

    def __init__(self,editSession,transition='inRight'):

        self._editSession = editSession

        self._R = R = bs.getResource('editGameListWindow')

        try: prevSelection = self._editSession._editUISelection
        except Exception: prevSelection = None

        self._width = 670
        self._height = 400 if gSmallUI else 470 if gMedUI else 540
        spacing = 40
        buttonWidth = 350

        topExtra = 20 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),
                                              transition=transition,
                                              scale=2.0 if gSmallUI else 1.3 if gMedUI else 1.0,
                                              stackOffset=(0,-16) if gSmallUI else (0,0))

        cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(35,self._height-60),scale=0.8,size=(175,60),
                                           autoSelect=True,label=bs.getResource('cancelText'),textScale=1.2)
        saveButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-195,self._height-60),scale=0.8,size=(190,60),
                                         autoSelect=True,leftWidget=cancelButton,label=bs.getResource('saveText'),textScale=1.2)
        bs.widget(edit=cancelButton,leftWidget=cancelButton,rightWidget=saveButton)
        
        t = bs.textWidget(parent=self._rootWidget,position=(-10,self._height-50),size=(self._width,25),
                          text=R.titleText,color=gTitleColor,scale=1.05,
                          hAlign="center",vAlign="center",maxWidth=270)

        v = self._height - 115

        self._scrollWidth = self._width-205
        
        bs.textWidget(parent=self._rootWidget,text=R.listNameText,position=(196,v+31),maxWidth=150,
                      color=(0.8,0.8,0.8,0.5),size=(0,0),scale=0.75,hAlign='right',vAlign='center')

        
        self._textField = bs.textWidget(parent=self._rootWidget,position=(210,v+7),size=(self._scrollWidth-53,43),
                                        text=self._editSession._name,hAlign="left",
                                        vAlign="center",
                                        maxChars=40,
                                        autoSelect=True,
                                        color=(0.9,0.9,0.9,1.0),
                                        description=R.listNameText,
                                        editable=True,padding=4,
                                        onReturnPressCall=self._savePressWithSound)
        bs.widget(edit=cancelButton,downWidget=self._textField)

        #v -= (scrollHeight+45)

        self._listWidgets = []

        h = 40
        v = self._height - 172
        hspacing = 17

        bColor = (0.6,0.53,0.63)
        bTextColor = (0.75,0.7,0.8)
        #h -= 80
        #v -= 40

        v -= 2
        v += 63

        s = 1.03 if gSmallUI else 1.36 if gMedUI else 1.74
        v -= 63.0*s
        
        addGameButton = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(110,61.0*s),
                                        onActivateCall=self._add,
                                        onSelectCall=bs.Call(self._setUISelection,'addButton'),
                                        autoSelect=True,
                                        buttonType='square',
                                        color=bColor,
                                        textColor=bTextColor,
                                        textScale=0.8,
                                        label=R.addGameText)
        #bs.widget(edit=cancelButton,downWidget=addGameButton)
        bs.widget(edit=addGameButton,upWidget=self._textField)
        v -= 63.0*s

        self._editButton = editGameButton = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(110,61.0*s),
                                                            onActivateCall=self._edit,
                                                            onSelectCall=bs.Call(self._setUISelection,'editButton'),
                                                            autoSelect=True,
                                                            buttonType='square',
                                                            color=bColor,
                                                            textColor=bTextColor,
                                                            textScale=0.8,
                                                            label=R.editGameText)
        v -= 63.0*s

        removeGameButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(110,61.0*s),
                                               textScale=0.8,
                                               onActivateCall=self._remove,
                                               autoSelect=True,
                                               buttonType='square',
                                               color=bColor,
                                               textColor=bTextColor,
                                               label=R.removeGameText)
        v -= 40
        h += 9
        moveUpButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(42,35),
                                           onActivateCall=self._moveUp,
                                           label=bs.getSpecialChar('upArrow'),
                                           buttonType='square',
                                           color=bColor,
                                           textColor=bTextColor,
                                           autoSelect=True,
                                           repeat=True)
        h += 52
        moveDownButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(42,35),
                                             onActivateCall=self._moveDown,
                                             autoSelect=True,
                                             buttonType='square',
                                             color=bColor,
                                             textColor=bTextColor,
                                             label=bs.getSpecialChar('downArrow'),
                                             repeat=True)

        v = self._height - 100
        scrollHeight = self._height - 155
        scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(160,v-scrollHeight),
                                       highlight=False,onSelectCall=bs.Call(self._setUISelection,'gameList'),
                                       size=(self._scrollWidth,(scrollHeight-15)))
        bs.widget(edit=scrollWidget,leftWidget=addGameButton,rightWidget=scrollWidget)
        self._columnWidget = bs.columnWidget(parent=scrollWidget)
        bs.widget(edit=self._columnWidget,upWidget=self._textField)
        
        for button in [addGameButton,editGameButton,removeGameButton]:
            bs.widget(edit=button,leftWidget=button,rightWidget=scrollWidget)

        #h += 100+hspacing

        self._refresh()

        bs.buttonWidget(edit=cancelButton,onActivateCall=self._cancel)
        bs.containerWidget(edit=self._rootWidget,cancelButton=cancelButton,selectedChild=scrollWidget)

        bs.buttonWidget(edit=saveButton,onActivateCall=self._savePress)
        bs.containerWidget(edit=self._rootWidget,startButton=saveButton)

        if prevSelection == 'addButton': bs.containerWidget(edit=self._rootWidget,selectedChild=addGameButton)
        elif prevSelection == 'editButton': bs.containerWidget(edit=self._rootWidget,selectedChild=editGameButton)
        elif prevSelection == 'gameList': bs.containerWidget(edit=self._rootWidget,selectedChild=scrollWidget)

    def _setUISelection(self,selection):
        self._editSession._editUISelection = selection

    def _cancel(self):
        bs.playSound(bs.getSound('powerdown01'))
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = PlaylistWindow(transition='inLeft',sessionType=self._editSession._sessionType,
                                                     selectPlaylist=self._editSession._existingPlaylist).getRootWidget()
    def _add(self):
        # store list name then tell the session to perform an add
        self._editSession._name = bs.textWidget(query=self._textField)
        self._editSession._addGamePressed()

    def _edit(self):
        # store list name then tell the session to perform an add
        self._editSession._name = bs.textWidget(query=self._textField)
        self._editSession._editGamePressed()

    # def _editWithSound(self):
        # bs.playSound(bs.getSound('swish'))
        # self._edit()
        
    def _savePress(self):
        newName = bs.textWidget(query=self._textField)
        if newName != self._editSession._existingPlaylist and newName in bs.getConfig()[self._editSession._configName+' Playlists']:
            bs.screenMessage(self._R.cantSaveAlreadyExistsText)
            bs.playSound(bs.getSound('error'))
            return
        if len(newName) == 0:
            bs.playSound(bs.getSound('error'))
            return
        if len(self._editSession._playlist) == 0:
            bs.screenMessage(self._R.cantSaveEmptyListText)
            bs.playSound(bs.getSound('error'))
            return
        if newName == self._editSession._defaultListName:
            bs.screenMessage(self._R.cantOverwriteDefaultText)
            bs.playSound(bs.getSound('error'))
            return

        # if we had an old one, delete it
        if self._editSession._existingPlaylist is not None:
            bsInternal._addTransaction({'type':'REMOVE_PLAYLIST',
                                        'playlistType':self._editSession._configName,
                                        'playlistName':self._editSession._existingPlaylist})
            #del bs.getConfig()[self._editSession._configName+' Playlists'][self._editSession._existingPlaylist]
        
        #print 'ADDING PLAYLIST',repr(self._editSession._configName),newName,self._editSession._playlist

        bsInternal._addTransaction({'type':'ADD_PLAYLIST',
                                    'playlistType':self._editSession._configName,
                                    'playlistName':newName,
                                    'playlist':copy.deepcopy(self._editSession._playlist)})
        bsInternal._runTransactions()
        # bs.getConfig()[self._editSession._configName+' Playlists'][newName] = self._editSession._playlist
        # bs.writeConfig()
        
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        bs.playSound(bs.getSound('gunCocking'))
        uiGlobals['mainMenuWindow'] = PlaylistWindow(transition='inLeft',sessionType=self._editSession._sessionType,
                                                     selectPlaylist=newName).getRootWidget()
    def _savePressWithSound(self):
        bs.playSound(bs.getSound('swish'))
        self._savePress()

    def _select(self,index):
        self._editSession._selectedIndex = index

    def _refresh(self):

        # need to grab this here as rebuilding the list will change it otherwise
        oldSelectionIndex = self._editSession._selectedIndex

        while len(self._listWidgets) > 0: self._listWidgets.pop().delete()
        for index,p in enumerate(self._editSession._playlist):

            try: desc = bsUtils.resolveTypeName(p['type']).getConfigDescriptionLocalized(p)
            except Exception:
                bs.printException()
                desc = "(invalid: '"+p['type']+"')"

            w = bs.textWidget(parent=self._columnWidget,size=(self._width-80,30),
                              onSelectCall=bs.Call(self._select,index),
                              alwaysHighlight=True,
                              color=(0.8,0.8,0.8,1.0),
                              padding=0,
                              maxWidth=self._scrollWidth*0.93,
                              text=desc,
                              #onActivateCall=self._editWithSound,
                              onActivateCall=self._editButton.activate,
                              vAlign='center',selectable=True)
            bs.widget(edit=w,showBufferTop=50,showBufferBottom=50)
            # wanna be able to jump up to the text field from the top one
            if index == 0: bs.widget(edit=w,upWidget=self._textField)
            self._listWidgets.append(w)
            if oldSelectionIndex == index:
                bs.columnWidget(edit=self._columnWidget,selectedChild=w,visibleChild=w)

    def _moveDown(self):
        if self._editSession._selectedIndex >= len(self._editSession._playlist)-1: return
        i = self._editSession._selectedIndex
        tmp = self._editSession._playlist[i]
        self._editSession._playlist[i] = self._editSession._playlist[i+1]
        self._editSession._playlist[i+1] = tmp
        self._editSession._selectedIndex += 1
        self._refresh()

    def _moveUp(self):
        if self._editSession._selectedIndex < 1: return
        i = self._editSession._selectedIndex
        tmp = self._editSession._playlist[i]
        self._editSession._playlist[i] = self._editSession._playlist[i-1]
        self._editSession._playlist[i-1] = tmp
        self._editSession._selectedIndex -= 1
        self._refresh()

    def _remove(self):
        if len(self._editSession._playlist) == 0: return
        del self._editSession._playlist[self._editSession._selectedIndex]
        if self._editSession._selectedIndex >= len(self._editSession._playlist): self._editSession._selectedIndex = len(self._editSession._playlist)-1
        bs.playSound(bs.getSound('shieldDown'))
        self._refresh()

def _setupPlaylistTypeVars(obj,sessionType):

    defaultListName = bs.getResource('defaultGameListNameText')
    defaultNewListName = bs.getResource('defaultNewGameListNameText')
    
    if issubclass(sessionType,bs.TeamsSession):

        playModeName = bs.getResource('playModes.teamsText',fallback='teamsText')

        # this uses a generic key now; use it on languages that no longer have the old key (may 2014)
        try: obj._defaultListName = bs.getResource('defaultTeamGameListNameText')
        except Exception: obj._defaultListName = defaultListName.replace('${PLAYMODE}',playModeName)
        
        # this uses a generic key now; use it on languages that no longer have the old key (may 2014)
        try: obj._defaultNewListName = bs.getResource('defaultNewTeamGameListNameText')
        except Exception: obj._defaultNewListName = defaultNewListName.replace('${PLAYMODE}',playModeName)
        
        #obj._defaultNewListName = bs.getResource('defaultNewTeamGameListNameText')
        obj._getDefaultListCall = bsUtils._getDefaultTeamsPlaylist
        obj._sessionTypeName = 'bs.TeamsSession'
        obj._configName = 'Team Tournament'
        obj._windowTitleName = bs.getResource('playModes.teamsText',fallback='teamsText')
        obj._sessionType = bs.TeamsSession
    elif issubclass(sessionType,bs.FreeForAllSession):

        playModeName = bs.getResource('playModes.freeForAllText',fallback='freeForAllText')
        
        # this uses a generic key now; use it on languages that no longer have the old key (may 2014)
        try: obj._defaultListName = bs.getResource('defaultFreeForAllGameListNameText')
        except Exception: obj._defaultListName = defaultListName.replace('${PLAYMODE}',playModeName)

        # this uses a generic key now; use it on languages that no longer have the old key (may 2014)
        try: obj._defaultNewListName = bs.getResource('defaultNewFreeForAllGameListNameText')
        except Exception: obj._defaultNewListName = defaultNewListName.replace('${PLAYMODE}',playModeName)
        
        #obj._defaultNewListName = bs.getResource('defaultNewFreeForAllGameListNameText')
        obj._getDefaultListCall = bsUtils._getDefaultFreeForAllPlaylist
        obj._sessionTypeName = 'bs.FreeForAllSession'
        obj._configName = 'Free-for-All'
        obj._windowTitleName = bs.getResource('playModes.freeForAllText',fallback='freeForAllText')
        obj._sessionType = bs.FreeForAllSession
    else: raise Exception('invalid session type: '+sessionType)


class GameListEditSession(object):

    def __init__(self,sessionType,existingPlaylist=None,transition='inRight',playlist=None,playlistName=None):

        bsConfig = bs.getConfig()
        
        # since we may be showing our map list momentarily,
        # lets go ahead and preload all map preview textures
        bsMap.preloadPreviewMedia()
        self._sessionType = sessionType
        _setupPlaylistTypeVars(self,sessionType)
        self._existingPlaylist = existingPlaylist

        self._configNameFull = self._configName+' Playlists'

        # make sure config exists
        if self._configNameFull not in bsConfig:
            bsConfig[self._configNameFull] = {}
            
        # try: self._playlists = bsConfig[self._configName+' Playlists']
        # except Exception: self._playlists = bsConfig[self._configName+' Playlists'] = {}

        self._selectedIndex = 0
        if existingPlaylist:
            self._name = existingPlaylist
            # filter out invalid games
            self._playlist = bsUtils._filterPlaylist(bsConfig[self._configName+' Playlists'][existingPlaylist],sessionType=sessionType,removeUnOwned=False)
        else:
            if playlist is not None: self._playlist = playlist
            else: self._playlist = []
            if playlistName is not None: self._name = playlistName
            else:
                # find a good unused name
                i = 1
                while True:
                    self._name = self._defaultNewListName+((' '+str(i)) if i > 1 else '')
                    if self._name not in bsConfig[self._configName+' Playlists']: break
                    i += 1
            # also we want it to come up with 'add' highlighted since its empty and thats all they can do
            self._editUISelection = 'addButton'

        uiGlobals['mainMenuWindow'] = EditPlaylistWindow(editSession=self,transition=transition).getRootWidget()

    def getSessionType(self):
        return self._sessionType

    def _addGamePressed(self):
        bs.containerWidget(edit=uiGlobals['mainMenuWindow'],transition='outLeft')
        uiGlobals['mainMenuWindow'] = AddGameWindow(editSession=self).getRootWidget()

    def _editGamePressed(self):
        if len(self._playlist) == 0: return
        self._showEditUI(gameType=bsUtils.resolveTypeName(self._playlist[self._selectedIndex]['type']),
                         config=self._playlist[self._selectedIndex])

    def _addGameCancelled(self):
        bs.containerWidget(edit=uiGlobals['mainMenuWindow'],transition='outRight')
        uiGlobals['mainMenuWindow'] = EditPlaylistWindow(editSession=self,transition='inLeft').getRootWidget()

    def _showEditUI(self,gameType,config):
        self._editingGame = (config is not None)
        self._editingGameType = gameType
        gameType.createConfigUI(self._sessionType,copy.deepcopy(config),self._editGameDone)

    def _addGameTypeSelected(self,gameType):
        self._showEditUI(gameType=gameType,config=None)

    def _editGameDone(self,config):
        if config is None:
            # if we were editing, go back to our list
            if self._editingGame:
                bs.playSound(bs.getSound('powerdown01'))
                bs.containerWidget(edit=uiGlobals['mainMenuWindow'],transition='outRight')
                uiGlobals['mainMenuWindow'] = EditPlaylistWindow(editSession=self,transition='inLeft').getRootWidget()
            # otherwise we were adding; go back to the add type choice list
            else:
                bs.containerWidget(edit=uiGlobals['mainMenuWindow'],transition='outRight')
                uiGlobals['mainMenuWindow'] = AddGameWindow(editSession=self,transition='inLeft').getRootWidget()
        else:
            # make sure type is in there..
            config['type'] = bsUtils.getTypeName(self._editingGameType)

            if self._editingGame:
                self._playlist[self._selectedIndex] = copy.deepcopy(config)
            else:
                # add a new entry to the playlist..
                insertIndex = min(len(self._playlist),self._selectedIndex+1)
                self._playlist.insert(insertIndex,copy.deepcopy(config))
                self._selectedIndex = insertIndex

            #if not self._editingGame:
            bs.playSound(bs.getSound('gunCocking'))
            bs.containerWidget(edit=uiGlobals['mainMenuWindow'],transition='outRight')
            uiGlobals['mainMenuWindow'] = EditPlaylistWindow(editSession=self,transition='inLeft').getRootWidget()


def standardGameConfigUI(gameClass,sessionType,config,completionCall):
    # replace the main window once we come up successfully
    prevWindow = uiGlobals['mainMenuWindow']
    uiGlobals['mainMenuWindow'] = GameSettingsSelectWindow(gameClass,sessionType,config,completionCall=completionCall).getRootWidget()
    bs.containerWidget(edit=prevWindow,transition='outLeft')
        

class PlaylistWindow(Window):

    def __init__(self,sessionType,transition='inRight',selectPlaylist=None,originWidget=None):

        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        global gMainWindow

        # store state for when we exit the next game..
        # if issubclass(sessionType,bs.TeamsSession): gMainWindow = "Team Game Select"
        # elif issubclass(sessionType,bs.FreeForAllSession): gMainWindow = "Free-for-All Game Select"
        # else: raise Exception('invalid sessionType: '+sessionType)

        self._sessionType = sessionType
        _setupPlaylistTypeVars(self,sessionType)

        self._maxPlaylists = 30
        
        self._R = R = bs.getResource('gameListWindow')

        self._width = 650
        self._height = 380 if gSmallUI else 420 if gMedUI else 500
        spacing = 40
        buttonWidth = 350
        topExtra = 20 if gSmallUI else 0
        
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale = 2.05 if gSmallUI else 1.5 if gMedUI else 1.0,
                                              stackOffset=(0,-10) if gSmallUI else (0,0))

        # self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-160,self._height-60),size=(160,68),scale=0.77,
        #                                                     autoSelect=True,textScale=1.3,label=bs.getResource('doneText'))
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(43,self._height-60),size=(160,68),scale=0.77,
                                                            autoSelect=True,textScale=1.3,label=bs.getResource('backText'),buttonType='back')
                                                            #autoSelect=True,textScale=1.3,label=bs.getResource('backText'),buttonType='back')
        # self._playButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-163,self._height-60),
        #                                        autoSelect=True,size=(160,64),scale=0.77,textScale=1.3,label=bs.getResource('playText'))
        t = bs.textWidget(parent=self._rootWidget,position=(0,self._height-47),
                          size=(self._width,25),
                          text=self._R.titleText.replace('${TYPE}',self._windowTitleName),color=gHeadingColor,
                          maxWidth=290,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(105,self._height-49))
        
        v = self._height - 59
        h = 41
        hspacing = 15
        bColor = (0.6,0.53,0.63)
        bTextColor = (0.75,0.7,0.8)

        #s = 0.97 if gSmallUI else 1.13 if gMedUI else 1.43
        #s = 1.08 if gSmallUI else 1.13 if gMedUI else 1.46
        s = 1.1 if gSmallUI else 1.27 if gMedUI else 1.57
        v -= 63.0*s
        newButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(90,58.0*s),
                                        onActivateCall=self._newPlaylist,
                                        color=bColor,
                                        autoSelect=True,
                                        buttonType='square',
                                        textColor=bTextColor,
                                        textScale=0.7,
                                        label=R.newText)

        v -= 63.0*s
        self._editButton = editButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(90,58.0*s),
                                                            onActivateCall=self._editPlaylist,
                                                            color=bColor,
                                                            autoSelect=True,
                                                            textColor=bTextColor,
                                                            buttonType='square',
                                                            textScale=0.7,
                                                            label=R.editText)

        v -= 63.0*s
        duplicateButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(90,58.0*s),
                                              onActivateCall=self._duplicatePlaylist,
                                              color=bColor,
                                              autoSelect=True,
                                              textColor=bTextColor,
                                              buttonType='square',
                                              textScale=0.7,
                                              label=R.duplicateText)

        v -= 63.0*s
        deleteButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(90,58.0*s),
                                           onActivateCall=self._deletePlaylist,
                                           color=bColor,
                                           autoSelect=True,
                                           textColor=bTextColor,
                                           buttonType='square',
                                           textScale=0.7,
                                           label=R.deleteText)


        v = self._height - 75
        self._scrollHeight = self._height - 119
        #if gSmallUI: self._scrollHeight -= 65
        scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=(140,v-self._scrollHeight),size=(self._width-180,self._scrollHeight+10),highlight=False)
        #bs.widget(edit=backButton,downWidget=scrollWidget,leftWidget=scrollWidget)
        #bs.widget(edit=backButton,downWidget=scrollWidget)
        c = self._columnWidget = bs.columnWidget(parent=scrollWidget)

        
        h = 145
        v = self._height - self._scrollHeight - 109


        
        try: self._doRandomizeVal = bs.getConfig()[self._configName+' Playlist Randomize']
        except Exception: self._doRandomizeVal = 0
        # def _cbCallback(val):
        #     self._doRandomizeVal = val
        # self._shuffleCheckBox = bs.checkBoxWidget(parent=self._rootWidget,position=(h,v+5),scale=0.7,size=(250,30),
        #                                           color=(0.5,0.5,0.7),
        #                                           autoSelect=True,text=R.shuffleGameOrderText,maxWidth=220,
        #                                           textColor=(0.8,0.8,0.8),value=self._doRandomizeVal,onValueChangeCall=_cbCallback)
        # bs.widget(edit=self._shuffleCheckBox,upWidget=scrollWidget)

        h += 210
        # try: showTutorial = bs.getConfig()['Show Tutorial']
        # except Exception: showTutorial = True
        # def _cbCallback(val):
        #     bs.getConfig()['Show Tutorial'] = val
        #     bs.writeConfig()
        # self._showTutorialCheckBox = cb = bs.checkBoxWidget(parent=self._rootWidget,position=(h,v+5),scale=0.7,size=(250,30),
        #                                                     color=(0.5,0.5,0.7),
        #                                                     autoSelect=True,text=R.showTutorialText,maxWidth=220,
        #                                                     textColor=(0.8,0.8,0.8),value=showTutorial,onValueChangeCall=_cbCallback)

        
        for b in [newButton,deleteButton,editButton,duplicateButton]:
            bs.widget(edit=b,rightWidget=scrollWidget)
        #bs.widget(edit=scrollWidget,leftWidget=editButton,rightWidget=self._playButton)
        bs.widget(edit=scrollWidget,leftWidget=newButton)
        #bs.widget(edit=backButton,downWidget=newButton)
        # bs.widget(edit=cb,upWidget=newButton)

        # for b in [duplicateButton,deleteButton]:
        #     bs.widget(edit=b,upWidget=scrollWidget,downWidget=cb2)
        # bs.widget(edit=cb2,upWidget=duplicateButton)

        # bs.widget(edit=self._playButton,downWidget=scrollWidget)
        
        # make sure config exists
        self._configNameFull = self._configName+' Playlists'

        if self._configNameFull not in bs.getConfig():
            bs.getConfig()[self._configNameFull] = {}
        
        # try: self._playlists = bs.getConfig()[self._configName+' Playlists']
        # except Exception: bs.getConfig()[self._configName+' Playlists'] = self._playlists = {}

        self._selectedPlaylist = None
        self._selectedPlaylistIndex = None
        self._playlistWidgets = []

        self._refresh(selectPlaylist=selectPlaylist)

        bs.buttonWidget(edit=backButton,onActivateCall=self._back)
        #bs.containerWidget(edit=self._rootWidget,cancelButton=backButton)
        bs.containerWidget(edit=self._rootWidget,cancelButton=backButton)

        # bs.buttonWidget(edit=self._playButton,onActivateCall=self._choosePlaylist)
        #bs.containerWidget(edit=self._rootWidget,startButton=self._playButton,selectedChild=scrollWidget)
        bs.containerWidget(edit=self._rootWidget,selectedChild=scrollWidget)

    def _back(self):
        if self._selectedPlaylist is not None:
            bs.getConfig()[self._configName+' Playlist Selection'] = self._selectedPlaylist
            #bs.getConfig()[self._configName+' Playlist Randomize'] = self._doRandomizeVal
            bs.writeConfig()

        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = TeamsWindow(transition='inLeft',sessionType=self._sessionType).getRootWidget()

    def _select(self,name,index):
        self._selectedPlaylist = name
        self._selectedPlaylistIndex = index


    def _runSelectedPlaylist(self):
        bsInternal._unlockAllInput()
        try:
            bsInternal._newHostSession(self._sessionType)
        except Exception:
            import bsMainMenu
            bs.printException("exception running session",self._sessionType)
            # drop back into a main menu session..
            bsInternal._newHostSession(bsMainMenu.MainMenuSession)

    def _choosePlaylist(self):

        if self._selectedPlaylist is None: return
        self._savePlaylistSelection()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

        bsInternal._fadeScreen(False,time=250,endCall=self._runSelectedPlaylist)
        bsInternal._lockAllInput()

    def _refresh(self,selectPlaylist=None):
        oldSelection = self._selectedPlaylist

        # if there was no prev selection, look in prefs
        if oldSelection is None:
            try: oldSelection = bs.getConfig()[self._configName+' Playlist Selection']
            except Exception: pass

        oldSelectionIndex = self._selectedPlaylistIndex

        # delete old
        while len(self._playlistWidgets) > 0: self._playlistWidgets.pop().delete()

        #items = self._playlists.items()
        items = bs.getConfig()[self._configNameFull].items()

        # make sure everything is unicode now
        items = [(i[0].decode('utf-8'),i[1]) if type(i[0]) is not unicode else i for i in items]
            
        items.sort(key=lambda x:x[0].lower())
        #items = [[self._defaultListName,None]] + items # default is always first
        items = [[u'__default__',None]] + items # default is always first
        index = 0
        for pName,p in items:
            #print 'ADDING',pName
            w = bs.textWidget(parent=self._columnWidget,size=(self._width-40,30),
                              maxWidth=self._width-110,
                              text=self._getPlaylistDisplayName(pName),
                              hAlign='left',vAlign='center',
                              color=(0.6,0.6,0.7,1.0) if pName == u'__default__' else (0.85,0.85,0.85,1),
                              alwaysHighlight=True,
                              onSelectCall=bs.Call(self._select,pName,index),
                              #onActivateCall=bs.Call(self._playButton.activate),
                              onActivateCall=bs.Call(self._editButton.activate),
                              selectable=True)
            bs.widget(edit=w,showBufferTop=50,showBufferBottom=50)
            # hitting up from top widget shoud jump to 'back;
            if index == 0: bs.widget(edit=w,upWidget=self._backButton)
            self._playlistWidgets.append(w)
            # select this one if the user requested it
            if selectPlaylist is not None:
                if pName == selectPlaylist:
                    bs.columnWidget(edit=self._columnWidget,selectedChild=w,visibleChild=w)
            else:
                # select this one if it was previously selected
                if oldSelectionIndex is not None: # go by index if there's one
                    if index == oldSelectionIndex:
                        bs.columnWidget(edit=self._columnWidget,selectedChild=w,visibleChild=w)
                else: # otherwise look by name
                    if pName == oldSelection:
                        bs.columnWidget(edit=self._columnWidget,selectedChild=w,visibleChild=w)

            index += 1
        # hitting down from the last widget should go to our first checkbox
        # bs.widget(edit=w,downWidget=self._shuffleCheckBox)

    def _savePlaylistSelection(self):
        # store the selected playlist in prefs..
        # this serves dual purposes of letting us re-select it next time
        # if we want and also lets us pass it to the game (since we reset the whole python environment thats not actually easy)
        bs.getConfig()[self._configName+' Playlist Selection'] = self._selectedPlaylist
        bs.getConfig()[self._configName+' Playlist Randomize'] = self._doRandomizeVal
        bs.writeConfig()

    def _newPlaylist(self):

        # clamp at our max playlist number
        if len(bs.getConfig()[self._configNameFull]) > self._maxPlaylists:
            bs.screenMessage(bs.translate('serverResponses','Max number of playlists reached.'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
        
        self._savePlaylistSelection() # in case they cancel so we can return to this state..
        GameListEditSession(sessionType=self._sessionType)
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _editPlaylist(self):
        if self._selectedPlaylist is None: return
        #if self._selectedPlaylist == self._defaultListName:
        if self._selectedPlaylist == '__default__':
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.cantEditDefaultText)
            return
        self._savePlaylistSelection()
        GameListEditSession(existingPlaylist=self._selectedPlaylist,sessionType=self._sessionType)
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _doDeletePlaylist(self):

        #print 'TO START WITH HAVE',bs.getConfig()['Team Tournament Playlists'].keys()
        bsInternal._addTransaction({'type':'REMOVE_PLAYLIST',
                                    'playlistType':self._configName,
                                    'playlistName':self._selectedPlaylist})
        bsInternal._runTransactions()
        #print 'AFTER HAVE',bs.getConfig()['Team Tournament Playlists'].keys()

        # try: del bs.getConfig()[self._configName+' Playlists'][self._selectedPlaylist]
        # except Exception: pass
        #bs.writeConfig()
        
        bs.playSound(bs.getSound('shieldDown'))

        # (we don't use len()-1 here because the default list adds one)
        if self._selectedPlaylistIndex > len(bs.getConfig()[self._configName+' Playlists']):
            self._selectedPlaylistIndex = len(bs.getConfig()[self._configName+' Playlists'])
        self._refresh()

    def _deletePlaylist(self):
        if self._selectedPlaylist is None: return
        #if self._selectedPlaylist == self._defaultListName:
        if self._selectedPlaylist == '__default__':
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.cantDeleteDefaultText)
        else:
            ConfirmWindow(self._R.deleteConfirmText.replace('${LIST}',self._selectedPlaylist),self._doDeletePlaylist,450,150)
    
    def _getPlaylistDisplayName(self,playlist):
        if playlist == '__default__':
            return self._defaultListName
        else: return playlist

    def _duplicatePlaylist(self):

        if self._selectedPlaylist is None: return
        #if self._selectedPlaylist == self._defaultListName:
        if self._selectedPlaylist == '__default__':
            pl = self._getDefaultListCall()
        else:
            #pl = self._playlists[self._selectedPlaylist]
            pl = bs.getConfig()[self._configNameFull][self._selectedPlaylist]

        # clamp at our max playlist number
        if len(bs.getConfig()[self._configNameFull]) > self._maxPlaylists:
            bs.screenMessage(bs.translate('serverResponses','Max number of playlists reached.'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return
            
        #copyWord = bs.getResource('copyText')
        copyText = bs.getResource('copyOfText')
        copyWord = copyText.replace('${NAME}','').strip() # get just 'Copy' or whatnot
        # find a valid dup name that doesn't exist

        testIndex = 1
        #copyStr = '' if copyWord in self._selectedPlaylist else ' '+copyWord
        baseName = self._getPlaylistDisplayName(self._selectedPlaylist)

        # if it looks like a copy, strip digits and spaces off the end
        if copyWord in baseName:
            while baseName[-1].isdigit() or baseName[-1] == ' ': baseName = baseName[:-1]
        while True:
            if copyWord in baseName: testName = baseName
            else: testName = copyText.replace('${NAME}',baseName)
            if testIndex > 1: testName += ' '+str(testIndex)
            #if not testName in self._playlists: break
            if not testName in bs.getConfig()[self._configNameFull]: break
            testIndex += 1

        bsInternal._addTransaction({'type':'ADD_PLAYLIST',
                                    'playlistType':self._configName,
                                    'playlistName':testName,
                                    'playlist':copy.deepcopy(pl)})
        bsInternal._runTransactions()
        # self._playlists[testName] = copy.deepcopy(pl)
        # bs.writeConfig()
        
        bs.playSound(bs.getSound('gunCocking'))
        self._refresh(selectPlaylist=testName)

class PlayOptionsWindow(PopupWindow):
    
    # def __del__(self):
    #     print '~PlayOptionsWindow()'

    def __init__(self,sessionType,playlist,transition='inScale',scaleOrigin=None,delegate=None):
        # print 'PlayOptionsWindow()'

        self._R = R = bs.getResource('gameListWindow')
        self._delegate = delegate

        
        # store state for when we exit the next game..
        # if issubclass(sessionType,bs.TeamsSession):
        #     gMainWindow = "Team Game Select"
        # elif issubclass(sessionType,bs.FreeForAllSession):
        #     gMainWindow = "Free-for-All Game Select"
        # else: raise Exception('invalid sessionType: '+sessionType)
        _setupPlaylistTypeVars(self,sessionType)

        #print 'GOT SESSION TYPE',sessionType,'PLAYLIST',playlist,'configname',self._configName
        
        self._transitioningOut = False
        
        try: self._doRandomizeVal = bs.getConfig()[self._configName+' Playlist Randomize']
        except Exception: self._doRandomizeVal = 0
        
        self._sessionType = sessionType
        self._playlist = playlist

        self._width = 500
        #self._width = 5+random.random()*600.0
        self._height = 330-50

        self._rowHeight = 45
        # grab our maps to dispaly..
        modelOpaque = bs.getModel('levelSelectButtonOpaque')
        modelTransparent = bs.getModel('levelSelectButtonTransparent')
        maskTex = bs.getTexture('mapPreviewMask')
        # poke into this playlist and see if we can display some of its maps..
        mapTextures = []
        mapTextureEntries = []
        rows = 0
        columns = 0
        gameCount = 0
        sc = 0.35
        cWidthTotal = 0
        try:
            maxColumns = 5
            name = playlist
            if name == '__default__':
                if self._sessionType is bs.FreeForAllSession: pl = bsUtils._getDefaultFreeForAllPlaylist()
                elif self._sessionType is bs.TeamsSession: pl = bsUtils._getDefaultTeamsPlaylist()
                else: raise Exception("unrecognized session-type: "+str(self._sessionType))
            else:
                try: pl = bs.getConfig()[self._configName+' Playlists'][name]
                except Exception:
                    print 'ERROR INFO: self._configName is:',self._configName
                    print 'ERROR INFO: playlist names are:',bs.getConfig()[self._configName+' Playlists'].keys()
                    raise
            pl = bsUtils._filterPlaylist(pl,self._sessionType,removeUnOwned=False,markUnOwned=True)
            gameCount = len(pl)
            for entry in pl:
                m = entry['settings']['map']
                try: mapType = bsMap.getMapClass(m)
                except Exception: mapType = None
                if mapType is not None:
                    texName = mapType.getPreviewTextureName()
                    if texName is not None:
                        mapTextures.append(texName)
                        mapTextureEntries.append(entry)
            rows = (max(0,len(mapTextures)-1)/maxColumns)+1
            columns = min(maxColumns,len(mapTextures))

            if len(mapTextures) == 1: sc = 1.1
            elif len(mapTextures) == 2: sc = 0.7
            elif len(mapTextures) == 3: sc = 0.55
            else: sc = 0.35
            self._rowHeight = 128.0*sc
            cWidthTotal = sc*250.0*columns
            if len(mapTextures) > 0:
                self._height += self._rowHeight * rows

        except Exception:
            bs.printException("error listing playlist maps")

        showShuffleCheckBox = True if gameCount > 1 else False

        if showShuffleCheckBox: self._height += 40
        
        # creates our _rootWidget
        scale = 1.69 if gSmallUI else 1.1 if gMedUI else 0.85
        PopupWindow.__init__(self,position=scaleOrigin,size=(self._width,self._height),scale=scale)
        
        # self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
        #                                       scale=1.69 if gSmallUI else 1.1 if gMedUI else 0.85,
        #                                       stackOffset=(0,0) if gSmallUI else (0,0),
        #                                       scaleOriginStackOffset=scaleOrigin)
        playlistName = self._defaultListName if playlist == '__default__' else playlist
        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-89+51),
                                        size=(0,0), text=playlistName, scale=1.4,
                                        color=(1,1,1),
                                        maxWidth=self._width*0.7,
                                        hAlign="center",vAlign="center")

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(25,self._height-53),size=(50,50),scale=0.7,
                                             label='',color=(0.42,0.73,0.2),
                                             # label='',color=(1,0,0),
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)


        hOffsImg = self._width*0.5-cWidthTotal*0.5
        vOffsImg = self._height - 118-sc*125.0+50
        self._haveAtLeastOneOwned = False
        for r in range(rows):
            for c in range(columns):
                texIndex = r*columns+c
                if texIndex < len(mapTextures):
                    texName = mapTextures[texIndex]
                    h = hOffsImg + sc * 250 * c
                    v = vOffsImg - self._rowHeight * r
                    entry = mapTextureEntries[texIndex]
                    owned = False if (('isUnOwnedMap' in entry and entry['isUnOwnedMap'])
                                      or ('isUnOwnedGame' in entry and entry['isUnOwnedGame'])) else True

                    if owned: self._haveAtLeastOneOwned = True
                    
                    try:
                        desc = bsUtils.resolveTypeName(entry['type']).getConfigDescriptionLocalized(entry)
                        if not owned: desc += '\n'+bs.getResource('unlockThisInTheStoreText')
                        descColor = (0,1,0) if owned else (1,0,0)
                    except Exception:
                        desc = '(invalid)'
                        descColor = (1,0,0)

                    
                    b = bs.buttonWidget(parent=self._rootWidget,size=(sc*240.0,sc*120.0),
                                    position=(h,v),
                                    texture=bs.getTexture(texName if owned else 'empty'),
                                    modelOpaque=modelOpaque if owned else None,
                                    onActivateCall=bs.Call(bs.screenMessage,desc,color=descColor),
                                    label='',color=(1,1,1),autoSelect=True,
                                    extraTouchBorderScale=0.0,
                                    modelTransparent=modelTransparent if owned else None,
                                    maskTexture=maskTex if owned else None)
                    if not owned:

                        # ewww; buttons dont currently have alpha so in this case we draw an image
                        # over our button with an empty texture on it
                        bs.imageWidget(parent=self._rootWidget,size=(sc*260.0,sc*130.0),
                                       position=(h-10.0*sc,v-4.0*sc),
                                       drawController=b,
                                       color=(1,1,1),
                                       texture=bs.getTexture(texName),
                                       modelOpaque=modelOpaque,
                                       opacity=0.25,
                                       modelTransparent=modelTransparent,
                                       maskTexture=maskTex)

                        bs.imageWidget(parent=self._rootWidget,size=(sc*100,sc*100),
                                       drawController=b,
                                       position=(h+sc*70,v+sc*10),
                                       texture=bs.getTexture('lock'))


        
        def _cbCallback(val):
            self._doRandomizeVal = val
            bs.getConfig()[self._configName+' Playlist Randomize'] = self._doRandomizeVal
            bs.writeConfig()

        if showShuffleCheckBox:
            self._shuffleCheckBox = bs.checkBoxWidget(parent=self._rootWidget,position=(110,200),scale=1.0,size=(250,30),
                                                      #color=(0.5,0.5,0.7),
                                                      autoSelect=True,text=R.shuffleGameOrderText,maxWidth=300,
                                                      textColor=(0.8,0.8,0.8),value=self._doRandomizeVal,onValueChangeCall=_cbCallback)

        try: showTutorial = bs.getConfig()['Show Tutorial']
        except Exception: showTutorial = True
        def _cbCallback(val):
            bs.getConfig()['Show Tutorial'] = val
            bs.writeConfig()
        self._showTutorialCheckBox = cb = bs.checkBoxWidget(parent=self._rootWidget,position=(110,151),scale=1.0,size=(250,30),
                                                            #color=(0.5,0.5,0.7),
                                                            autoSelect=True,text=R.showTutorialText,maxWidth=300,
                                                            textColor=(0.8,0.8,0.8),value=showTutorial,onValueChangeCall=_cbCallback)
        
        self._playButton = bs.buttonWidget(parent=self._rootWidget,position=(70,44),size=(200,45),scale=1.8,
                                           textResScale=1.5,
                                           onActivateCall=self._onPlayPress,autoSelect=True,label=bs.getResource('playText'))

        bs.widget(edit=self._playButton,upWidget=self._showTutorialCheckBox)
        
        bs.containerWidget(edit=self._rootWidget,startButton=self._playButton,
                           cancelButton=self._cancelButton,selectedChild=self._playButton)

        # update now and once per second..
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._update()

        
    def _doesTargetPlaylistExist(self):
        if self._playlist == '__default__': return True
        try: return (self._playlist in bs.getConfig()[self._configName+' Playlists'])
        except Exception: return False
        
    def _update(self):
        # all we do here is make sure our targeted playlist still exists..
        # and close ourself if not..
        if not self._doesTargetPlaylistExist():
            self._transitionOut()
        
    def _transitionOut(self,transition='outScale'):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition=transition)

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()
            
    def _onCancelPress(self):
        self._transitionOut()
        
    def _onPlayPress(self):

        # disallow if our playlist has disappeared..
        if not self._doesTargetPlaylistExist(): return

        # disallow if we have no unlocked games
        if not self._haveAtLeastOneOwned:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('playlistNoValidGamesErrorText'),color=(1,0,0))
            return
        
        bs.getConfig()[self._configName+' Playlist Selection'] = self._playlist
        bs.writeConfig()
        bsInternal._fadeScreen(False,time=250,endCall=self._runSelectedPlaylist)
        bsInternal._lockAllInput()
        self._transitionOut(transition='outLeft')
        if self._delegate is not None:
            self._delegate.onPlayOptionsWindowRunGame()

    def _runSelectedPlaylist(self):
        bsInternal._unlockAllInput()
        try:
            bsInternal._newHostSession(self._sessionType)
        except Exception:
            import bsMainMenu
            bs.printException("exception running session",self._sessionType)
            # drop back into a main menu session..
            bsInternal._newHostSession(bsMainMenu.MainMenuSession)
        
class TeamsWindow(Window):
    
    # def __del__(self):
    #     print '~TeamsWindow()'

    def __init__(self,sessionType,transition='inRight',originWidget=None):
        # print 'TeamsWindow()'

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        global gMainWindow
        # store state for when we exit the next game..
        if issubclass(sessionType,bs.TeamsSession):
            gMainWindow = "Team Game Select"
            bsInternal._setAnalyticsScreen('Teams Window')
        elif issubclass(sessionType,bs.FreeForAllSession):
            gMainWindow = "Free-for-All Game Select"
            bsInternal._setAnalyticsScreen('FreeForAll Window')
        else: raise Exception('invalid sessionType: '+sessionType)
        _setupPlaylistTypeVars(self,sessionType)

        self._sessionType = sessionType

        #print 'FOO IS', bsInternal._getAccountMiscReadVal('foo',123)
        
        # on new installations, lets go ahead and create a few playlists besides the hard-coded default one:
        if not bsInternal._getAccountMiscVal('madeStandardPlaylists',False):
            bsInternal._addTransaction({'type':'ADD_PLAYLIST',
                                        'playlistType':'Free-for-All',
                                        'playlistName':bs.getResource('singleGamePlaylistNameText').replace('${GAME}',bs.translate('gameNames','Death Match')),
                                        'playlist':[{'settings':{'Epic Mode':False,'Kills to Win Per Player':10,'Respawn Times':1.0,'Time Limit':300,'map':'Doom Shroom'},
                                                     'type':'bsDeathMatch.DeathMatchGame'},
                                                    {'settings':{'Epic Mode':False,'Kills to Win Per Player':10,'Respawn Times':1.0,'Time Limit':300,'map':'Crag Castle'},
                                                     'type':'bsDeathMatch.DeathMatchGame'}]})
            bsInternal._addTransaction({'type':'ADD_PLAYLIST',
                                        'playlistType':'Team Tournament',
                                        'playlistName':bs.getResource('singleGamePlaylistNameText').replace('${GAME}',bs.translate('gameNames','Capture the Flag')),
                                        'playlist':[{'type': 'bsCaptureTheFlag.CTFGame',
                                                     'settings': {'map': 'Bridgit', 'Score to Win': 3, 'Flag Idle Return Time': 30,'Flag Touch Return Time': 0,
                                                                  'Respawn Times': 1.0, 'Time Limit': 600,'Epic Mode': False}},
                                                    {'type': 'bsCaptureTheFlag.CTFGame',
                                                     'settings': {'map': 'Roundabout', 'Score to Win': 2, 'Flag Idle Return Time': 30, 'Flag Touch Return Time': 0,
                                                                  'Respawn Times': 1.0, 'Time Limit': 600, 'Epic Mode': False}},
                                                    {'type': 'bsCaptureTheFlag.CTFGame',
                                                     'settings': {'map': 'Tip Top', 'Score to Win': 2, 'Flag Idle Return Time': 30, 'Flag Touch Return Time': 3,
                                                                  'Respawn Times': 1.0, 'Time Limit': 300, 'Epic Mode': False}}]})
            bsInternal._addTransaction({'type':'ADD_PLAYLIST',
                                        'playlistType':'Team Tournament',
                                        'playlistName':bs.translate('playlistNames','Just Sports'),
                                        'playlist':[{'type': 'bsHockey.HockeyGame',
                                                     'settings': {'Time Limit': 0, 'map': 'Hockey Stadium', 'Score to Win': 1, 'Respawn Times': 1.0}},
                                                    {'type': 'bsFootball.FootballTeamGame',
                                                     'settings': {'Time Limit': 0, 'map': 'Football Stadium', 'Score to Win': 21, 'Respawn Times': 1.0}}]})
            bsInternal._addTransaction({'type':'ADD_PLAYLIST',
                                        'playlistType':'Free-for-All',
                                        'playlistName':bs.translate('playlistNames','Just Epic'),
                                        'playlist':[{'type': 'bsElimination.EliminationGame',
                                                     'settings': {'Time Limit': 120, 'map': 'Tip Top', 'Respawn Times': 1.0, 'Lives Per Player': 1, 'Epic Mode': 1}}]})
            
            bsInternal._addTransaction({'type':'SET_MISC_VAL','name':'madeStandardPlaylists','value':True})
            bsInternal._runTransactions()
        
        # get the current selection (if any)
        try: self._selectedPlaylist = bs.getConfig()[self._configName+' Playlist Selection']
        except Exception: self._selectedPlaylist = None

        self._width = 800
        self._height = 480 if gSmallUI else 510 if gMedUI else 580

        topExtra = 20 if gSmallUI else 0
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=1.69 if gSmallUI else 1.3 if gMedUI else 1.0,
                                              stackOffset=(0,-26) if gSmallUI else (0,10))
        self._backButton = bs.buttonWidget(parent=self._rootWidget,position=(59,self._height-70),size=(120,60),scale=1.0,
                                           onActivateCall=self._onBackPress,autoSelect=True,label=bs.getResource('backText'),
                                           buttonType='back')
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._backButton)
        t = self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-41),size=(0,0),
                                            text=self._windowTitleName,scale=1.3,resScale=1.5,
                                            color=gHeadingColor,
                                            hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=self._backButton,buttonType='backSmall',size=(60,54),position=(59,self._height-67),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(135,self._height-41))
        
        self._scrollWidth = self._width - 100
        self._scrollHeight = self._height - 136
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,highlight=False,
                                             size=(self._scrollWidth,self._scrollHeight),
                                             position=((self._width-self._scrollWidth)*0.5,65))
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)

        self._subContainer = None

        self._configNameFull = self._configName+' Playlists'
        self._lastConfig = None

        # update now and once per second.. (this should do our initial refresh)
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._update()
        
        
    def _refresh(self):

        if not self._rootWidget.exists(): return
        
        if self._subContainer is not None:
            self._saveState()
            self._subContainer.delete()

        # make sure config exists
        if self._configNameFull not in bs.getConfig():
            bs.getConfig()[self._configNameFull] = {}
        
        # make sure config exists
        # try: self._playlists = bs.getConfig()[self._configName+' Playlists']
        # except Exception: bs.getConfig()[self._configName+' Playlists'] = self._playlists = {}
        
        #items = self._playlists.items()
        items = bs.getConfig()[self._configNameFull].items()

        # make sure everything is unicode
        items = [(i[0].decode('utf-8'),i[1]) if type(i[0]) is not unicode else i for i in items]
            
        items.sort(key=lambda x:x[0].lower())
        items = [[u'__default__',None]] + items # default is always first
        
        count = len(items)
        columns = 3
        rows = int(math.ceil(float(count)/columns))
        buttonWidth = 230
        buttonHeight = 230
        buttonBufferH = -3
        buttonBufferV = 0

        #self._subWidth = self._scrollWidth*0.95
        self._subWidth = self._scrollWidth
        self._subHeight = 40+rows*(buttonHeight+2*buttonBufferV) + 90
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._subWidth,self._subHeight),
                                                background=False)
        
        children = self._subContainer.getChildren()
        for c in children: c.delete()
        
        bs.textWidget(parent=self._subContainer,text=bs.getResource('playlistsText'),position=(10,self._subHeight - 26),
                      size=(0,0),scale=1.0,maxWidth=400,color=gTitleColor,
                      hAlign='left',vAlign='center')
        
        index = 0
        maskTexture=bs.getTexture('characterIconMask')
        tintColor=(1,1,1)
        tint2Color=(1,1,1)
        selectedCharacter=None
        bsConfig = bs.getConfig()

        modelOpaque = bs.getModel('levelSelectButtonOpaque')
        modelTransparent = bs.getModel('levelSelectButtonTransparent')
        maskTex = bs.getTexture('mapPreviewMask')

        hOffs = 225 if count == 1 else 115 if count == 2 else 0
        hOffsBottom = 0 if (count > 1 and count%3 == 1) else 230
        
        for y in range(rows):
            for x in range(columns):
                name = items[index][0]
                pos = (x*(buttonWidth+2*buttonBufferH)+buttonBufferH+8+hOffs,
                       self._subHeight - 47 - (y+1)*(buttonHeight+2*buttonBufferV))
                #if (x == 0 and y == 0): pos = (self._subWidth*0.5-buttonWidth*0.5,0)
                b = bs.buttonWidget(parent=self._subContainer,buttonType='square',
                                    size=(buttonWidth,buttonHeight),
                                    #scale= 0.01 if (x == 0 and y == 0) else 1.0,
                                    autoSelect=True,
                                    label='',
                                    position=pos)
                # if x == 0 and y == 0:
                #     print 'POS IS',pos
                #     print 'size is',(buttonWidth,buttonHeight)
                #     print 'CENTER IS',b.getScreenSpaceCenter()
                bs.buttonWidget(edit=b,onActivateCall=bs.Call(self._onPlaylistPress,b,name),
                                onSelectCall=bs.Call(self._onPlaylistSelect,name))
                bs.widget(edit=b,showBufferTop=50,showBufferBottom=50)
                
                if self._selectedPlaylist == name:
                    bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)
                
                if y == 0: bs.widget(edit=b,upWidget=self._backButton)
                if x == 0: bs.widget(edit=b,leftWidget=self._backButton)
                
                # if self._spazzes[index] == selectedCharacter:
                #     bs.containerWidget(edit=self._subContainer,selectedChild=b,visibleChild=b)
                #name = bs.translate('characterNames',self._spazzes[index])
                if name == '__default__': printName = self._defaultListName
                else: printName = name
                bs.textWidget(parent=self._subContainer,text=printName,position=(pos[0]+buttonWidth*0.5,pos[1]+buttonHeight*0.79),
                              size=(0,0),scale=buttonWidth*0.003,maxWidth=buttonWidth*0.7,
                              drawController=b,hAlign='center',vAlign='center')

                # poke into this playlist and see if we can display some of its maps..
                mapImages = []
                try:
                    mapTextures = []
                    mapTextureEntries = []
                    if name == '__default__':
                        if self._sessionType is bs.FreeForAllSession: playlist = bsUtils._getDefaultFreeForAllPlaylist()
                        elif self._sessionType is bs.TeamsSession: playlist = bsUtils._getDefaultTeamsPlaylist()
                        else: raise Exception("unrecognized session-type: "+str(self._sessionType))
                    else:
                        if name not in bsConfig[self._configName+' Playlists']:
                            print 'NOT FOUND ERR',bsConfig[self._configName+' Playlists']
                        playlist = bsConfig[self._configName+' Playlists'][name]
                    playlist = bsUtils._filterPlaylist(playlist,self._sessionType,removeUnOwned=False,markUnOwned=True)
                    for entry in playlist:
                        m = entry['settings']['map']
                        try: mapType = bsMap.getMapClass(m)
                        except Exception: mapType = None
                        if mapType is not None:
                            texName = mapType.getPreviewTextureName()
                            if texName is not None:
                                mapTextures.append(texName)
                                mapTextureEntries.append(entry)
                        if len(mapTextures) >= 6: break

                    #sc = 0.37 if len(mapTextures) == 1 else 0.33 if len(mapTextures) == 2 else 0.3

                    if len(mapTextures) > 4:
                        imgRows = 3
                        imgColumns = 2
                        sc = 0.33
                        hOffsImg = 30
                        vOffsImg = 126
                    elif len(mapTextures) > 2:
                        imgRows = 2
                        imgColumns = 2
                        sc = 0.35
                        hOffsImg = 24
                        vOffsImg = 110
                    elif len(mapTextures) > 1:
                        imgRows = 2
                        imgColumns = 1
                        sc = 0.5
                        hOffsImg = 47
                        vOffsImg = 105
                    else:
                        imgRows = 1
                        imgColumns = 1
                        sc = 0.75
                        hOffsImg = 20
                        vOffsImg = 65

                    for r in range(imgRows):
                        for c in range(imgColumns):
                            texIndex = r*imgColumns+c
                            if texIndex < len(mapTextures):
                                entry = mapTextureEntries[texIndex]

                                owned = False if (('isUnOwnedMap' in entry and entry['isUnOwnedMap'])
                                                  or ('isUnOwnedGame' in entry and entry['isUnOwnedGame'])) else True
                                
                                texName = mapTextures[texIndex]
                                h = pos[0]+hOffsImg + sc * 250 * c
                                v = pos[1]+vOffsImg - sc * 130 * r
                                mapImages.append(bs.imageWidget(parent=self._subContainer,size=(sc*250.0,sc*125.0),
                                                                position=(h,v),
                                                                texture=bs.getTexture(texName),
                                                                opacity=1.0 if owned else 0.25,
                                                                drawController=b,
                                                                modelOpaque=modelOpaque,
                                                                modelTransparent=modelTransparent,
                                                                maskTexture=maskTex))
                                if not owned:
                                    bs.imageWidget(parent=self._subContainer,size=(sc*100.0,sc*100.0),
                                                   position=(h+sc*75,v+sc*10),
                                                   texture=bs.getTexture('lock'),
                                                   drawController=b)
                                
                        v -= sc*130.0
                        #h += 12
                        #sc -= 0.03

                except Exception:
                    bs.printException("error listing playlist maps")
                    
                if len(mapImages) == 0:
                    bs.textWidget(parent=self._subContainer,text='???',scale=1.5,size=(0,0),color=(1,1,1,0.5),
                                  hAlign='center',vAlign='center',
                                  drawController=b,position=(pos[0]+buttonWidth*0.5,pos[1]+buttonHeight*0.5))
                    
                index += 1
                
                if index >= count: break
            if index >= count: break
        self._customizeButton = b = bs.buttonWidget(parent=self._subContainer,
                                                    size=(180,50),position=(21+hOffsBottom,34),
                                                    textScale=0.65,
                                                    label=bs.getResource('customizeText'),
                                                    onActivateCall=self._onCustomizePress,
                                                    color=(0.54,0.52,0.67),
                                                    textColor=(0.7,0.65,0.7),
                                                    autoSelect=True)
        bs.widget(edit=b,showBufferTop=22,showBufferBottom=28)
        self._restoreState()

    def onPlayOptionsWindowRunGame(self):
        if not self._rootWidget.exists():
            return
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _onPlaylistSelect(self,playlistName):
        self._selectedPlaylist = playlistName

    def _update(self):

        # make sure config exists
        if self._configNameFull not in bs.getConfig():
            bs.getConfig()[self._configNameFull] = {}

        c = bs.getConfig()[self._configNameFull]
        if c != self._lastConfig:
            self._lastConfig = copy.deepcopy(c)
            self._refresh()
        
        
    def _onPlaylistPress(self,button,playlistName):
        # (make sure the target playlist still exists)
        try: exists = (playlistName == '__default__' or playlistName in bs.getConfig()[self._configNameFull])
        except Exception: exists = False
        if not exists: return
        
        self._saveState()
        PlayOptionsWindow(sessionType=self._sessionType,scaleOrigin=button.getScreenSpaceCenter(),
                          playlist=playlistName,delegate=self)
        
    def _onCustomizePress(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = PlaylistWindow(originWidget=self._customizeButton,sessionType=self._sessionType).getRootWidget()
        
    def _onBackPress(self):

        # store our selected playlist if that's changed..
        if self._selectedPlaylist is not None:
            try: prevSel = bs.getConfig()[self._configName+' Playlist Selection']
            except Exception: prevSel = None
            if self._selectedPlaylist != prevSel:
                bs.getConfig()[self._configName+' Playlist Selection'] = self._selectedPlaylist
                bs.writeConfig()

        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = PlayWindow(transition='inLeft').getRootWidget()

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._backButton: selName = 'Back'
            elif sel == self._scrollWidget:
                subsel = self._subContainer.getSelectedChild()
                if subsel == self._customizeButton: selName = 'Customize'
                else: selName = 'Scroll'
            else: raise Exception("unrecognized selected widget")
            gWindowStates[self.__class__.__name__] = selName
        except Exception:
            bs.printException('error saving state for',self.__class__)
    
    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]
            except Exception: selName = None
            if selName == 'Back': sel = self._backButton
            elif selName == 'Scroll': sel = self._scrollWidget
            elif selName == 'Customize':
                sel = self._scrollWidget
                bs.containerWidget(edit=self._subContainer,selectedChild=self._customizeButton,visibleChild=self._customizeButton)
            else: sel = self._scrollWidget
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)
        
class PlayWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):
        newStyle = True
        width = 800
        height = 550 if newStyle else 400
        spacing = 90
        buttonWidth = 400

        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        R = bs.getResource('playWindow')

        self._rootWidget = bs.containerWidget(size=(width,height),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=(1.6 if newStyle else 1.52) if gSmallUI else 1.2 if gMedUI else 0.9,
                                              stackOffset=((0,0) if newStyle else (10,7)) if gSmallUI else (0,0))
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                            position=(55, height-132) if newStyle else (55,height-92),
                                                            size=(120,60),scale=1.1,
                                                            textResScale=1.5,
                                                            textScale=1.2,autoSelect=True,
                                                            label=bs.getResource('backText'),buttonType='back')

        t = bs.textWidget(parent=self._rootWidget,
                          position=(width*0.5,height-(101 if newStyle else 61)),
                          size=(0,0),
                          text=R.titleText,
                          scale=1.7,
                          resScale=2.0,
                          maxWidth=400,
                          color=gHeadingColor,
                          hAlign="center",vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(140,height-(101 if newStyle else 61)))
        
        v = height - (110 if newStyle else 60)
        v -= 100
        c = (0.6,0.7,0.6,1.0)
        v -= 280 if newStyle else 180
        hoffs = 80 if newStyle else 0
        sc = 1.13 if newStyle else 0.68

        self._lineupTex = bs.getTexture('playerLineup')
        angryComputerTransparentModel = bs.getModel('angryComputerTransparent')
        self._lineup1TransparentModel = bs.getModel('playerLineup1Transparent')
        self._lineup2TransparentModel = bs.getModel('playerLineup2Transparent')
        self._lineup3TransparentModel = bs.getModel('playerLineup3Transparent')
        self._lineup4TransparentModel = bs.getModel('playerLineup4Transparent')
        self._eyesModel = bs.getModel('plasticEyesTransparent')

        self._coopButton = b = bs.buttonWidget(parent=self._rootWidget,position=(hoffs,v+(sc*15 if newStyle else 0)),size=(sc*buttonWidth,sc*(300 if newStyle else 360)),
                                               extraTouchBorderScale=0.1,
                                               autoSelect=True,label="", buttonType='square', textScale=1.13, onActivateCall=self._coop)

        self._drawDude(0,b,hoffs,v,sc,position=(140,30),color=(0.72,0.4,1.0))
        self._drawDude(1,b,hoffs,v,sc,position=(185,53),color=(0.71,0.5,1.0))
        self._drawDude(2,b,hoffs,v,sc,position=(220,27),color=(0.67,0.44,1.0))
        self._drawDude(3,b,hoffs,v,sc,position=(255,57),color=(0.7,0.3,1.0))
        bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(230),v+sc*(153)),size=(sc*115,sc*115),texture=self._lineupTex,modelTransparent=angryComputerTransparentModel)

        bs.textWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(-10),v+sc*(95)),size=(sc*buttonWidth,sc*50),
                      text=bs.getResource('playModes.singlePlayerCoopText',fallback='playModes.coopText'),
                      maxWidth=sc*buttonWidth*0.7,
                      resScale=1.5,
                      hAlign='center',vAlign='center',
                      color=(0.7,0.9,0.7,1.0),scale=sc*2.3)

        bs.textWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(-10),v+(sc*54)),size=(sc*buttonWidth,sc*30),
                      text=R.oneToFourPlayersText,hAlign='center',vAlign='center',
                      scale=0.83 * sc,flatness=1.0,
                      maxWidth=sc*buttonWidth*0.7,
                      color=c)

        sc = 0.5 if newStyle else 0.68
        hoffs += 440 if newStyle else 260
        v += 180 if newStyle else 0
        
        self._teamsButton = b = bs.buttonWidget(parent=self._rootWidget,position=(hoffs,v+(sc*15 if newStyle else 0)),size=(sc*buttonWidth,sc*(300 if newStyle else 360)),
                                                extraTouchBorderScale=0.1,
                                                autoSelect=True,label="", buttonType='square', textScale=1.13, onActivateCall=self._teamTourney)

        xx = -14
        self._drawDude(2,b,hoffs,v,sc,position=(xx+148,30),color=(0.2,0.4,1.0))
        self._drawDude(3,b,hoffs,v,sc,position=(xx+181,53),color=(0.3,0.4,1.0))
        self._drawDude(1,b,hoffs,v,sc,position=(xx+216,33),color=(0.3,0.5,1.0))
        self._drawDude(0,b,hoffs,v,sc,position=(xx+245,57),color=(0.3,0.5,1.0))

        xx = 155
        self._drawDude(0,b,hoffs,v,sc,position=(xx+151,30),color=(1.0,0.5,0.4))
        self._drawDude(1,b,hoffs,v,sc,position=(xx+189,53),color=(1.0,0.58,0.58))
        self._drawDude(3,b,hoffs,v,sc,position=(xx+223,27),color=(1.0,0.5,0.5))
        self._drawDude(2,b,hoffs,v,sc,position=(xx+257,57),color=(1.0,0.5,0.5))

        bs.textWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(-10),v+sc*(95)),size=(sc*buttonWidth,sc*50),
                      text=bs.getResource('playModes.teamsText',fallback='teamsText'),
                      resScale=1.5,
                      maxWidth=sc*buttonWidth*0.7,
                      hAlign='center',vAlign='center',
                      color=(0.7,0.9,0.7,1.0),scale=sc*2.3)
        bs.textWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(-10),v+(sc*54)),size=(sc*buttonWidth,sc*30),
                      text=R.twoToEightPlayersText,hAlign='center',vAlign='center',
                      resScale=1.5,
                      scale=0.9 * sc,flatness=1.0,
                      maxWidth=sc*buttonWidth*0.7,
                      color=c)

        hoffs += 0 if newStyle else 260
        v -= 155 if newStyle else 0
        self._freeForAllButton = b = bs.buttonWidget(parent=self._rootWidget,position=(hoffs,v+(sc*15 if newStyle else 0)),size=(sc*buttonWidth,sc*(300 if newStyle else 360)),
                                                     extraTouchBorderScale=0.1,
                                                     autoSelect=True,label="", buttonType='square', textScale=1.13, onActivateCall=self._freeForAll)

        xx = -5
        self._drawDude(0,b,hoffs,v,sc,position=(xx+140,30),color=(0.4,1.0,0.4))
        self._drawDude(3,b,hoffs,v,sc,position=(xx+185,53),color=(1.0,0.4,0.5))
        self._drawDude(1,b,hoffs,v,sc,position=(xx+220,27),color=(0.4,0.5,1.0))
        self._drawDude(2,b,hoffs,v,sc,position=(xx+255,57),color=(0.5,1.0,0.4))
        xx = 140
        self._drawDude(2,b,hoffs,v,sc,position=(xx+148,30),color=(1.0,0.9,0.4))
        self._drawDude(0,b,hoffs,v,sc,position=(xx+182,53),color=(0.7,1.0,0.5))
        self._drawDude(3,b,hoffs,v,sc,position=(xx+233,27),color=(0.7,0.5,0.9))
        self._drawDude(1,b,hoffs,v,sc,position=(xx+266,53),color=(0.4,0.5,0.8))
        bs.textWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(-10),v+sc*(95)),size=(sc*buttonWidth,sc*50),
                      text=bs.getResource('playModes.freeForAllText',fallback='freeForAllText'),
                      maxWidth=sc*buttonWidth*0.7,
                      hAlign='center',vAlign='center',
                      color=(0.7,0.9,0.7,1.0),scale=sc*1.9)
        bs.textWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(-10),v+(sc*54)),size=(sc*buttonWidth,sc*30),
                      text=R.twoToEightPlayersText,hAlign='center',vAlign='center',
                      scale=0.9 * sc,flatness=1.0,
                      maxWidth=sc*buttonWidth*0.7,
                      color=c)

        bs.buttonWidget(edit=backButton,onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=backButton,selectedChild=self._coopButton)

        bs.widget(edit=backButton)
        # selected = None
        # try:
        #     global gGameTypeSelection
        #     if gGameTypeSelection == 'Team Games': selected = self._teamsButton
        #     elif gGameTypeSelection == 'Free-for-All Games': selected = self._freeForAllButton
        #     elif gGameTypeSelection == 'Co-op Games': selected = self._coopButton
        #     else: raise Exception("unknown selection type: "+gGameTypeSelection)
        # except Exception,e:
        #     print 'Err in PlayWindow select restore:',e

        # if selected is not None:
        #     bs.containerWidget(edit=self._rootWidget,selectedChild=selected)
        self._restoreState()
        
        # bs.textWidget(parent=self._rootWidget,position=(width*0.5,40),size=(200,50),editable=True,
        #               text='foobar',hAlign='right',vAlign='center',maxWidth=50)
        # bs.textWidget(parent=self._rootWidget,position=(width*0.5,40),size=(200,50),editable=True,
        #               text='foobarifficreallylong',hAlign='right',vAlign='center')
        # bs.textWidget(parent=self._rootWidget,position=(width*0.5,40),size=(200,50),editable=True,scale=0.7,
        #               text='foobar',hAlign='left',vAlign='bottom',color=(1,0,0,1))

    def _back(self):
        self._saveState()
        uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)

    def _coop(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = CoopWindow(originWidget=self._coopButton).getRootWidget()

    def _teamTourney(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        #uiGlobals['mainMenuWindow'] = PlaylistWindow(transition='inRight',sessionType=bs.TeamsSession).getRootWidget()
        uiGlobals['mainMenuWindow'] = TeamsWindow(originWidget=self._teamsButton,sessionType=bs.TeamsSession).getRootWidget()

    def _freeForAll(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        #uiGlobals['mainMenuWindow'] = PlaylistWindow(transition='inRight',sessionType=bs.FreeForAllSession).getRootWidget()
        uiGlobals['mainMenuWindow'] = TeamsWindow(originWidget=self._freeForAllButton,sessionType=bs.FreeForAllSession).getRootWidget()

    def _drawDude(self,i,b,hoffs,v,sc,position,color):
        hExtra = -100
        vExtra = 130
        eyeColor = (0.7*1.0+0.3*color[0],
                    0.7*1.0+0.3*color[1],
                    0.7*1.0+0.3*color[2])
        if i == 0:
            t = bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]),v+sc*(vExtra+position[1])),size=(sc*60,sc*80),color=color,
                               texture=self._lineupTex,modelTransparent=self._lineup1TransparentModel)
            bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]+12),v+sc*(vExtra+position[1]+53)),size=(sc*36,sc*18),texture=self._lineupTex,color=eyeColor,modelTransparent=self._eyesModel)
        elif i == 1:
            t = bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]),v+sc*(vExtra+position[1])),size=(sc*45,sc*90),color=color,
                               texture=self._lineupTex,modelTransparent=self._lineup2TransparentModel)
            bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]+5),v+sc*(vExtra+position[1]+67)),size=(sc*32,sc*16),texture=self._lineupTex,color=eyeColor,modelTransparent=self._eyesModel)
        elif i == 2:
            t = bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]),v+sc*(vExtra+position[1])),size=(sc*45,sc*90),color=color,
                               texture=self._lineupTex,modelTransparent=self._lineup3TransparentModel)
            bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]+5),v+sc*(vExtra+position[1]+59)),size=(sc*34,sc*17),texture=self._lineupTex,color=eyeColor,modelTransparent=self._eyesModel)
        elif i == 3:
            t = bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]),v+sc*(vExtra+position[1])),size=(sc*48,sc*96),color=color,
                               texture=self._lineupTex,modelTransparent=self._lineup4TransparentModel)
            bs.imageWidget(parent=self._rootWidget,drawController=b,position=(hoffs+sc*(hExtra+position[0]+2),v+sc*(vExtra+position[1]+62)),size=(sc*38,sc*19),texture=self._lineupTex,color=eyeColor,modelTransparent=self._eyesModel)

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._teamsButton: selName = 'Team Games'
            elif sel == self._coopButton: selName = 'Co-op Games'
            elif sel == self._freeForAllButton: selName = 'Free-for-All Games'
            elif sel == self._backButton: selName = 'Back'
            else: raise Exception("unrecognized selected widget")
            gWindowStates[self.__class__.__name__] = selName
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]
            except Exception: selName = None
            if selName == 'Team Games': sel = self._teamsButton
            elif selName == 'Co-op Games': sel = self._coopButton
            elif selName == 'Free-for-All Games': sel = self._freeForAllButton
            elif selName == 'Back': sel = self._backButton
            else: sel = self._coopButton
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)
        
class LockedErrorWindow(Window):

    def __init__(self,name,depName):
        width = 550
        height = 250
        lockTex = bs.getTexture('lock')
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight',scale=1.7 if gSmallUI else 1.3 if gMedUI else 1.0)
        t = bs.textWidget(parent=self._rootWidget,position=(150-20,height*0.63),size=(0,0),
                          hAlign="left",
                          vAlign='center',
                          text=bs.getResource('levelIsLockedText').replace('${LEVEL}',name),
                          maxWidth=400,
                          color=(1,0.8,0.3,1),scale=1.1)
        t = bs.textWidget(parent=self._rootWidget,position=(150-20,height*0.48),size=(0,0),
                          hAlign="left",
                          vAlign='center',
                          text=bs.getResource('levelMustBeCompletedFirstText').replace('${LEVEL}',depName),
                          maxWidth=400,
                          color=gInfoTextColor,scale=0.8)
        bs.imageWidget(parent=self._rootWidget,position=(56-20,height*0.39),size=(80,80),texture=lockTex,opacity=1.0)
        b = bs.buttonWidget(parent=self._rootWidget,position=((width-140)/2,30),
                            size=(140,50),label=bs.getResource('okText'),onActivateCall=self._ok)
        bs.containerWidget(edit=self._rootWidget,selectedChild=b,startButton=b)
        bs.playSound(bs.getSound('error'))
    def _ok(self):
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')


class AchievementsWindow(PopupWindow):

    def __init__(self,position,scale=None):

        # self._onCloseCall = onCloseCall
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        self._transitioningOut = False
        
        self._width = 450
        self._height = 300 if gSmallUI else 370 if gMedUI else 450

        bgColor = (0.5,0.4,0.6)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor)

        env = bs.getEnvironment()

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        achievements = bsAchievement.gAchievements
        numComplete = len([a for a in achievements if a.isComplete()])
        
        txtFinal = bs.getResource('accountSettingsWindow.achievementProgressText').replace('${COUNT}',str(numComplete)).replace('${TOTAL}',str(len(achievements)))
        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-20),size=(0,0),hAlign='center',vAlign='center',
                                        scale=0.6,text=txtFinal,
                                        maxWidth=200,color=(1,1,1,0.4))

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._width-60,self._height-70),position=(30,30),captureArrows=True,simpleCullingV=10)
        bs.widget(edit=self._scrollWidget,autoSelect=True)

        # self._loadingText = bs.textWidget(parent=self._scrollWidget,
        #                                   #position=(subWidth*0.1-10,subHeight-20-incr*i),
        #                                   #maxWidth=subWidth*0.1,
        #                                   scale=0.5,
        #                                   text=bs.getResource('loadingText')+'...',
        #                                   size=(self._width-60,100),
        #                                   hAlign='center',vAlign='center')
                
        
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)

        incr = 36
        subWidth = self._width-90
        subHeight = 40+len(achievements)*incr

        eqText = bs.getResource('coopSelectWindow.powerRankingPointsEqualsText')
        ptsText = bs.getResource('coopSelectWindow.powerRankingPointsText')
        
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(subWidth,subHeight),background=False)

        totalPts = 0
        for i,ach in enumerate(achievements):
            complete = ach.isComplete()
            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.08-5,subHeight-20-incr*i),
                          maxWidth=20,
                          scale=0.5,
                          color=(0.6,0.6,0.7) if complete else (0.6,0.6,0.7,0.2),
                          flatness=1.0,shadow=0.0,
                          text=str(i+1),
                          size=(0,0),
                          hAlign='right',vAlign='center')

            bs.imageWidget(parent=self._subContainer,
                           position=(subWidth*0.10+1,subHeight-20-incr*i-9) if complete else (subWidth*0.10-4,subHeight-20-incr*i-14),
                           size=(18,18) if complete else (27,27),
                           opacity = 1.0 if complete else 0.3,
                           color=ach.getIconColor(complete)[:3],
                           texture=ach.getIconTexture(complete))
            if complete:
                bs.imageWidget(parent=self._subContainer,
                               position=(subWidth*0.10-4,subHeight-25-incr*i-9),
                               size=(28,28),
                               color=(2,1.4,0),
                               texture=bs.getTexture('achievementOutline'))
            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.19,subHeight-19-incr*i+3),
                          maxWidth=subWidth*0.62,
                          scale=0.6,flatness=1.0,shadow=0.0,
                          color=(1,1,1) if complete else (1,1,1,0.2),
                          text=ach.getNameLocalized(),
                          size=(0,0),
                          hAlign='left',vAlign='center')

            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.19,subHeight-19-incr*i-10),
                          maxWidth=subWidth*0.62,
                          scale=0.4,flatness=1.0,shadow=0.0,
                          color=(0.83,0.8,0.85) if complete else (0.8,0.8,0.8,0.2),
                          text=ach.getDescriptionFullCompleteLocalized() if complete else ach.getDescriptionFullLocalized(),
                          size=(0,0),
                          hAlign='left',vAlign='center')
            
            pts = ach.getPowerRankingValue()
            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.92,subHeight-20-incr*i),
                          maxWidth=subWidth*0.15,
                          color=(0.7,0.8,1.0) if complete else (0.9,0.9,1.0,0.3),flatness=1.0,shadow=0.0,
                          scale=0.6,
                          text=ptsText.replace('${NUMBER}',str(pts)),
                          size=(0,0),
                          hAlign='center',vAlign='center')
            if complete:
                totalPts += pts

                
        bs.textWidget(parent=self._subContainer,
                      position=(subWidth*1.0,subHeight-20-incr*len(achievements)),
                      maxWidth=subWidth*0.5,
                      scale=0.7,
                      color=(0.7,0.8,1.0),flatness=1.0,shadow=0.0,
                      text=bs.getResource('coopSelectWindow.totalText')+' '+eqText.replace('${NUMBER}',str(totalPts)),
                      size=(0,0),
                      hAlign='right',vAlign='center')
            
        

    def _onCancelPress(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            #self._saveState()
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            # if self._onCloseCall is not None:
            #     self._onCloseCall()

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()

class TrophiesWindow(PopupWindow):

    def __init__(self,position,data,scale=None):

        self._data = data
        
        # self._onCloseCall = onCloseCall
        if scale is None: scale = 2.3 if gSmallUI else 1.65 if gMedUI else 1.23
        self._transitioningOut = False
        
        self._width = 300
        #self._height = 300 if gSmallUI else 370 if gMedUI else 450
        self._height = 300

        bgColor = (0.5,0.4,0.6)
        
        # creates our _rootWidget
        PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor)

        env = bs.getEnvironment()

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-20),size=(0,0),hAlign='center',vAlign='center',
                                        scale=0.6,text=bs.getResource('trophiesText'),maxWidth=200,color=(1,1,1,0.4))

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._width-60,self._height-70),position=(30,30),captureArrows=True)
        bs.widget(edit=self._scrollWidget,autoSelect=True)

        # self._loadingText = bs.textWidget(parent=self._scrollWidget,
        #                                   #position=(subWidth*0.1-10,subHeight-20-incr*i),
        #                                   #maxWidth=subWidth*0.1,
        #                                   scale=0.5,
        #                                   text=bs.getResource('loadingText')+'...',
        #                                   size=(self._width-60,100),
        #                                   hAlign='center',vAlign='center')
                
        
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)

        incr = 31
        #achievements = bsAchievement.gAchievements
        subWidth = self._width-90

        trophyTypes = [
            ['0a'],
            ['0b'],
            ['1'],
            ['2'],
            ['3'],
            ['4'],
            ]
        subHeight = 40+len(trophyTypes)*incr

        eqText = bs.getResource('coopSelectWindow.powerRankingPointsEqualsText')
        
        self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(subWidth,subHeight),background=False)

        totalPts = 0

        #eqText = bs.getResource('coopSelectWindow.powerRankingPointsEqualsText')
        ptsText = bs.getResource('coopSelectWindow.powerRankingPointsText')
        multText = bs.getResource('coopSelectWindow.powerRankingPointsMultText')
        numText = bs.getResource('numberText')

        #print 'data is',self._data
        
        for i,trophyType in enumerate(trophyTypes):
            tCount = self._data['t'+trophyType[0]]
            tMult = self._data['t'+trophyType[0]+'m']
            have = True if tCount > 0 else False
            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.15,subHeight-20-incr*i),
                          scale=0.7,flatness=1.0,shadow=0.7,
                          color=(1,1,1),
                          text=bs.getSpecialChar('trophy'+trophyType[0]),
                          size=(0,0),
                          hAlign='center',vAlign='center')

            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.31,subHeight-20-incr*i),
                          maxWidth=subWidth*0.2,
                          scale=0.8,flatness=1.0,shadow=0.0,
                          color=(0,1,0) if have else (0.6,0.6,0.6,0.5),
                          text=str(tCount),
                          size=(0,0),
                          hAlign='center',vAlign='center')

            t = multText.replace('${NUMBER}',str(tMult))
            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.57,subHeight-20-incr*i),
                          maxWidth=subWidth*0.3,
                          scale=0.4,flatness=1.0,shadow=0.0,
                          color=(0.63,0.6,0.75) if have else (0.6,0.6,0.6,0.4),
                          text=t,
                          size=(0,0),
                          hAlign='center',vAlign='center')

            pts = tCount*tMult
            bs.textWidget(parent=self._subContainer,
                          position=(subWidth*0.88,subHeight-20-incr*i),
                          maxWidth=subWidth*0.3,
                          color=(0.7,0.8,1.0) if have else (0.9,0.9,1.0,0.3),flatness=1.0,shadow=0.0,
                          scale=0.5,
                          text=eqText.replace('${NUMBER}',str(pts)),
                          size=(0,0),
                          hAlign='center',vAlign='center')
            totalPts += pts
            
        # for i,ach in enumerate(achievements):
        #     complete = ach.isComplete()
        #     bs.textWidget(parent=self._subContainer,
        #                   position=(subWidth*0.08-5,subHeight-20-incr*i),
        #                   maxWidth=20,
        #                   scale=0.5,
        #                   color=(0.6,0.6,0.7) if complete else (0.6,0.6,0.7,0.2),
        #                   flatness=1.0,shadow=0.0,
        #                   text=str(i+1),
        #                   size=(0,0),
        #                   hAlign='right',vAlign='center')

        #     bs.imageWidget(parent=self._subContainer,
        #                    position=(subWidth*0.10+1,subHeight-20-incr*i-9) if complete else (subWidth*0.10-4,subHeight-20-incr*i-14),
        #                    size=(18,18) if complete else (27,27),
        #                    opacity = 1.0 if complete else 0.3,
        #                    color=ach.getIconColor(complete)[:3],
        #                    texture=ach.getIconTexture(complete))
        #     if complete:
        #         bs.imageWidget(parent=self._subContainer,
        #                        position=(subWidth*0.10-4,subHeight-25-incr*i-9),
        #                        size=(28,28),
        #                        color=(2,1.4,0),
        #                        texture=bs.getTexture('achievementOutline'))
        #     bs.textWidget(parent=self._subContainer,
        #                   position=(subWidth*0.19,subHeight-19-incr*i+3),
        #                   maxWidth=subWidth*0.62,
        #                   scale=0.6,flatness=1.0,shadow=0.0,
        #                   color=(1,1,1) if complete else (1,1,1,0.2),
        #                   text=ach.getNameLocalized(),
        #                   size=(0,0),
        #                   hAlign='left',vAlign='center')

        #     bs.textWidget(parent=self._subContainer,
        #                   position=(subWidth*0.19,subHeight-19-incr*i-10),
        #                   maxWidth=subWidth*0.62,
        #                   scale=0.4,flatness=1.0,shadow=0.0,
        #                   color=(0.83,0.8,0.85) if complete else (0.8,0.8,0.8,0.2),
        #                   text=ach.getDescriptionFullCompleteLocalized() if complete else ach.getDescriptionFullLocalized(),
        #                   size=(0,0),
        #                   hAlign='left',vAlign='center')
            
        #     pts = ach.getPowerRankingValue()
        #     bs.textWidget(parent=self._subContainer,
        #                   position=(subWidth*0.92,subHeight-20-incr*i),
        #                   maxWidth=subWidth*0.15,
        #                   color=(0.7,0.8,1.0) if complete else (0.9,0.9,1.0,0.3),flatness=1.0,shadow=0.0,
        #                   scale=0.6,
        #                   text=eqText.replace('${NUMBER}',str(pts)),
        #                   size=(0,0),
        #                   hAlign='center',vAlign='center')
        #     if complete:
        #         totalPts += pts

                
        bs.textWidget(parent=self._subContainer,
                      position=(subWidth*1.0,subHeight-20-incr*len(trophyTypes)),
                      maxWidth=subWidth*0.5,
                      scale=0.7,
                      color=(0.7,0.8,1.0),flatness=1.0,shadow=0.0,
                      text=bs.getResource('coopSelectWindow.totalText')+' '+eqText.replace('${NUMBER}',str(totalPts)),
                      size=(0,0),
                      hAlign='right',vAlign='center')
            
        

    def _onCancelPress(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            #self._saveState()
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            # if self._onCloseCall is not None:
            #     self._onCloseCall()

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()

        
class PowerRankingWindow(Window):
    
    # def __del__(self):
    #     print '~PowerRankingWindow()'
        
    def __init__(self,transition='inRight',modal=False,originWidget=None):
        #print 'PowerRankingWindow()'

        bsInternal._setAnalyticsScreen('League Window')
        
        self._powerRankingInfo = None
        self._modal = modal

        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._width = 1120
        self._height = 657 if gSmallUI else 710 if gMedUI else 800
        self._R = R = bs.getResource('coopSelectWindow')
        topExtra = 20 if gSmallUI else 0

        self._leagueURLArg = ''

        self._isCurrentSeason = False
        self._canDoMoreButton = True
        
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),
                                              stackOffset=(0,-15) if gSmallUI else (0,10) if gMedUI else (0,0),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale = 1.2 if gSmallUI else 0.93 if gMedUI else 0.8)
        
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(75,self._height-87-(4 if gSmallUI else 0)),size=(120,60),scale=1.2,
                                               autoSelect=True,label=bs.getResource('doneText' if self._modal else 'backText'),buttonType=None if self._modal else 'back',
                                               onActivateCall=self._back)

        # self._titleText = bs.textWidget(parent=self._rootWidget,scale=1.0,color=(0.5,0.7,0.5),text='POWER RANKING MOFO',
        #                               size=(0,0),position=(self._width*0.5,self._height-29),
        #                               maxWidth=self._width*0.7,hAlign='center',vAlign='center')

        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height - 56),size=(0,0),
                                         #text=self._R.powerRankingText,
                                         text=bs.getResource('league.leagueRankText',fallback='coopSelectWindow.powerRankingText'),
                                         hAlign="center",color=gTitleColor,scale=1.4,maxWidth=600,
                                         vAlign="center")

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',position=(75,self._height-87-(2 if gSmallUI else 0)),size=(60,55),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=self._titleText,hAlign='left',position=(165,self._height - 56))
        
        self._scrollWidth = self._width-130
        self._scrollHeight = self._height-160
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,highlight=False,position=(65,70),size=(self._scrollWidth,self._scrollHeight),centerSmallContent=True)
        bs.widget(edit=self._scrollWidget,autoSelect=True)
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._backButton,selectedChild=self._backButton)

        self._lastPowerRankingQueryTime = None
        self._doingPowerRankingQuery = False
        
        self._subContainer = None
        self._subContainerWidth = 800
        self._subContainerHeight = 483
        self._powerRankingScoreWidgets = []

        self._seasonPopupMenu = None
        self._requestedSeason = None
        self._season = None
        
        # take note of our account state; we'll refresh later if this changes
        self._accountState = bsInternal._getAccountState()

        self._refresh()
        self._restoreState()

        # if we've got cached power-ranking data already, display it
        info = _getCachedPowerRankingInfo()
        if info is not None:
            self._updateForPowerRankingInfo(info)

        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._update(show = True if info is None else False)
        
    def _onAchievementsPress(self):
        # only allow this for all-time or the current season
        # (we currently don't keep specific achievement data for old seasons)
        if self._season == 'a' or self._isCurrentSeason:
            AchievementsWindow(position=self._powerRankingAchievementsButton.getScreenSpaceCenter())
        else:
            bs.screenMessage(bs.getResource('achievementsUnavailableForOldSeasonsText',fallback='unavailableText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))


    def _onActivityMultPress(self):
        t = bs.getResource('coopSelectWindow.activenessAllTimeInfoText' if self._season == 'a' else 'coopSelectWindow.activenessInfoText').replace('${MAX}',str(bsInternal._getAccountMiscReadVal('activenessMax',1.0)))
        ConfirmWindow(t,cancelButton=False,width=460,height=150,originWidget=self._activityMultButton)

    def _onProMultPress(self):
        t = (bs.getResource('coopSelectWindow.proMultInfoText')
             .replace('${PERCENT}',str(bsInternal._getAccountMiscReadVal('proPowerRankingBoost',10)))
             .replace('${PRO}',
                      bs.getResource('store.bombSquadProNameText').replace('${APP_NAME}',bs.getResource('titleText'))))
        ConfirmWindow(t,cancelButton=False,width=460,height=130,originWidget=self._proMultButton)
        
    def _onTrophiesPress(self):
        #info = _getCachedPowerRankingInfo()
        info = self._powerRankingInfo
        if info is not None:
            TrophiesWindow(position=self._powerRankingTrophiesButton.getScreenSpaceCenter(),data=info)
        else:
            bs.playSound(bs.getSound('error'))
        
    def _onPowerRankingQueryResponse(self,data):
        self._doingPowerRankingQuery = False
        # important: *only* cache this if we requested the current season..
        if data is not None and data.get('s',None) is None:
            _cachePowerRankingInfo(data)
        # always store a copy locally though (even for other seasons)
        self._powerRankingInfo = copy.deepcopy(data)
        self._updateForPowerRankingInfo(data)
            
        
    def _saveState(self):
        pass
    
    def _restoreState(self):
        pass
    
    def _update(self, show=False):

        #print 'updating',bs.getRealTime()
        curTime = bs.getRealTime()

        # if our account state has changed, refresh our UI
        accountState = bsInternal._getAccountState()
        if accountState != self._accountState:
            self._accountState = accountState
            self._saveState()
            self._refresh()
            
            # and power ranking too...
            if not self._doingPowerRankingQuery: self._lastPowerRankingQueryTime = None

        # send off a new power-ranking query if its been long enough or our requested season has changed or whatnot..
        if not self._doingPowerRankingQuery and (self._lastPowerRankingQueryTime is None
                                                 #or self._season != self._requestedSeason
                                                 or curTime-self._lastPowerRankingQueryTime > 30000):
            try:
                if show:
                    bs.textWidget(edit=self._leagueTitleText,text='')
                    bs.textWidget(edit=self._leagueText,text='')
                    bs.textWidget(edit=self._leagueNumberText,text='')
                    bs.textWidget(edit=self._yourPowerRankingText,text=bs.getResource('loadingText')+'...')
                    bs.textWidget(edit=self._toRankedText,text='')
                    bs.textWidget(edit=self._powerRankingRankText,text='')
                    bs.textWidget(edit=self._seasonEndsText,text='')
                    bs.textWidget(edit=self._trophyCountsResetText,text='')
            except Exception,e:
                print 'EXC showing pr update msg',e
                
            self._lastPowerRankingQueryTime = curTime
            self._doingPowerRankingQuery = True
            bsInternal._powerRankingQuery(season=self._requestedSeason,callback=bs.WeakCall(self._onPowerRankingQueryResponse))
            
            
    def _refresh(self):
        
        # (re)create the sub-container if need be..
        if self._subContainer is not None: self._subContainer.delete()
        self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,size=(self._subContainerWidth,self._subContainerHeight),background=False)

        wParent = self._subContainer
        hBase = 6
        hSpacing = 200
        customButtons = []
        h = 0
        v = self._subContainerHeight - 20
        v2 = -2

        v -= 0

        h2 = 80
        v2 = v - 60
        countColor = (0.5,1.0,0.5)
        worthColor = (0.6,0.6,0.65)
        tallyColor = (0.5,0.6,0.8)
        spc = 43

        hOffsCount = 50
        hOffsPts = 140
        hOffsTally = 150
        ptsScale = 0.65
        ptsMaxWidth = 60
        tallyMaxWidth = 120
        countMaxWidth = 40
        hOffsIcons = -29
        iconScale = 1.4
        
        eqText = self._R.powerRankingPointsEqualsText
        numText = bs.getResource('numberText')

        
        v2 -= 70

        bs.textWidget(parent=wParent,position=(h2-60,v2+106),size=(0,0),flatness=1.0,shadow=0.0,
                                               text=bs.getResource('coopSelectWindow.pointsText'),hAlign='left',vAlign='center',scale=0.8,color=(1,1,1,0.3),maxWidth=200)
        
        self._powerRankingAchievementsButton = bs.buttonWidget(parent=wParent,position=(h2-60,v2+10),size=(200,80),icon=bs.getTexture('achievementsIcon'),
                                                               autoSelect=True,
                                                               onActivateCall=bs.WeakCall(self._onAchievementsPress),
                                                               upWidget=self._backButton,leftWidget=self._backButton,
                                                               color=(0.5,0.5,0.6),textColor=(0.7,0.7,0.8),
                                                               label='')
        
        self._powerRankingAchievementTotalText = bs.textWidget(parent=wParent,position=(h2+hOffsTally,v2+45),size=(0,0),flatness=1.0,shadow=0.0,
                                                               text='-',hAlign='left',vAlign='center',scale=0.8,color=tallyColor,maxWidth=tallyMaxWidth)
        
        v2 -= 80

        self._powerRankingTrophiesButton = bs.buttonWidget(parent=wParent,position=(h2-60,v2+10),size=(200,80),icon=bs.getTexture('medalSilver'),
                                                           autoSelect=True,
                                                           onActivateCall=bs.WeakCall(self._onTrophiesPress),
                                                           leftWidget=self._backButton,
                                                           color=(0.5,0.5,0.6),textColor=(0.7,0.7,0.8),
                                                           label='')
        self._powerRankingTrophiesTotalText = bs.textWidget(parent=wParent,position=(h2+hOffsTally,v2+45),size=(0,0),flatness=1.0,shadow=0.0,
                                                            text='-',hAlign='left',vAlign='center',scale=0.8,color=tallyColor,maxWidth=tallyMaxWidth)
        
        v2 -= 100

        bs.textWidget(parent=wParent,position=(h2-60,v2+86),size=(0,0),flatness=1.0,shadow=0.0,
                                               text=bs.getResource('coopSelectWindow.multipliersText'),hAlign='left',vAlign='center',scale=0.8,color=(1,1,1,0.3),maxWidth=200)
        
        self._activityMultButton = bs.buttonWidget(parent=wParent,position=(h2-60,v2+10),size=(200,60),icon=bs.getTexture('heart'),iconColor=(0.5,0,0.5),
                                                   label=bs.getResource('coopSelectWindow.activityText'),
                                                   autoSelect=True,
                                                   onActivateCall=bs.WeakCall(self._onActivityMultPress),
                                                   leftWidget=self._backButton,
                                                   color=(0.5,0.5,0.6),textColor=(0.7,0.7,0.8))
        
        self._activityMultText = bs.textWidget(parent=wParent,position=(h2+hOffsTally,v2+40),size=(0,0),flatness=1.0,shadow=0.0,
                                               text='-',hAlign='left',vAlign='center',scale=0.8,color=tallyColor,maxWidth=tallyMaxWidth)
        v2 -= 65

        
        self._proMultButton = bs.buttonWidget(parent=wParent,position=(h2-60,v2+10),size=(200,60),icon=bs.getTexture('logo'),iconColor=(0.3,0,0.3),
                                                   label=bs.getResource('store.bombSquadProNameText').replace('${APP_NAME}',bs.getResource('titleText')),
                                                   autoSelect=True,
                                                   onActivateCall=bs.WeakCall(self._onProMultPress),
                                                   leftWidget=self._backButton,
                                                   color=(0.5,0.5,0.6),textColor=(0.7,0.7,0.8))
        
        self._proMultText = bs.textWidget(parent=wParent,position=(h2+hOffsTally,v2+40),size=(0,0),flatness=1.0,shadow=0.0,
                                               text='-',hAlign='left',vAlign='center',scale=0.8,color=tallyColor,maxWidth=tallyMaxWidth)
        v2 -= 30
        
        v2 -= spc
        bs.textWidget(parent=wParent,position=(h2+hOffsTally-10-40,v2+35),size=(0,0),flatness=1.0,shadow=0.0,
                      text=bs.getResource('finalScoreText'),hAlign='right',vAlign='center',scale=0.9,color=worthColor,maxWidth=150)
        self._powerRankingTotalText = bs.textWidget(parent=wParent,position=(h2+hOffsTally-40,v2+35),size=(0,0),flatness=1.0,shadow=0.0,
                                                    text='-',hAlign='left',vAlign='center',scale=0.9,color=tallyColor,maxWidth=tallyMaxWidth)

        self._seasonShowText = bs.textWidget(parent=wParent,position=(390-15,v-20),size=(0,0),color=(0.6,0.6,0.7),maxWidth=200,
                                              text=bs.getResource('showText'),hAlign='right',vAlign='center',scale=0.8,shadow=0,flatness=1.0)
        # self._seasonPopupMenu = PopupMenu(parent=self._subContainer,position=(390,v-45),width=150,buttonSize=(200,50),
        #                                   choices=['Current Season (2)','Season 1',
        #                                            'Season A','Season B','Season C','Season D','Season E','Season F','Season G','All Time'],
        #                                   onValueChangeCall=self._onSeasonChange,
        #                                   #choicesDisplay=[bs.getResource(a) for a in ['randomText','playModes.teamsText','playModes.freeForAllText']],
        #                                   currentChoice='Season 2')
        
        self._leagueTitleText = bs.textWidget(parent=wParent,position=(470,v-97),size=(0,0),color=(0.6,0.6,0.7),maxWidth=230,
                                              text='',hAlign='center',vAlign='center',scale=0.9,shadow=0,flatness=1.0)

        # self._leagueButton = bs.buttonWidget(parent=wParent,position=(474-135,v-190),size=(270,130),label='',buttonType='square',
        #                                      autoSelect=True,color=(0.5,0.5,0.6))

        self._leagueTextScale = 1.8
        self._leagueTextMaxWidth = 210
        self._leagueText = bs.textWidget(parent=wParent,position=(470,v-140),size=(0,0),color=(1,1,1),maxWidth=self._leagueTextMaxWidth,
                                         text='-',hAlign='center',vAlign='center',scale=self._leagueTextScale,shadow=1.0,flatness=1.0)
        self._leagueNumberBasePos = (470,v-140)
        self._leagueNumberText = bs.textWidget(parent=wParent,position=(470,v-140),size=(0,0),color=(1,1,1),maxWidth=100,
                                               text='',hAlign='left',vAlign='center',scale=0.8,shadow=1.0,flatness=1.0)
        
        self._yourPowerRankingText = bs.textWidget(parent=wParent,position=(470,v-142-70),size=(0,0),color=(0.6,0.6,0.7),maxWidth=230,
                                                   text='',hAlign='center',vAlign='center',scale=0.9,shadow=0,flatness=1.0)

        self._toRankedText = bs.textWidget(parent=wParent,position=(470,v-250-70),size=(0,0),color=(0.6,0.6,0.7),maxWidth=230,
                                           text='',hAlign='center',vAlign='center',scale=0.8,shadow=0,flatness=1.0)
        
        self._powerRankingRankText = bs.textWidget(parent=wParent,position=(473,v-210-70),size=(0,0),big=False,
                                                   text='-',hAlign='center',vAlign='center',scale=1.0)

        self._seasonEndsText = bs.textWidget(parent=wParent,position=(470,v-380),size=(0,0),color=(0.6,0.6,0.6),maxWidth=230,
                                         text='',hAlign='center',vAlign='center',scale=0.9,shadow=0,flatness=1.0)
        self._trophyCountsResetText = bs.textWidget(parent=wParent,position=(470,v-410),size=(0,0),color=(0.5,0.5,0.5),maxWidth=230,
                                                    text=('Trophy counts will reset next season.'),hAlign='center',vAlign='center',scale=0.8,shadow=0,flatness=1.0)
        
        # for w in self._powerRankingScoreWidgets: w.delete()
        self._powerRankingScoreWidgets = []

        self._powerRankingScoreV = v - 56
        
        h = 707
        v -= 451

        self._seeMoreButton = bs.buttonWidget(parent=wParent,label=self._R.seeMoreText,position=(h,v),
                                              color=(0.5,0.5,0.6),textColor=(0.7,0.7,0.8),
                                              size=(230,60),autoSelect=True,
                                              onActivateCall=bs.WeakCall(self._onMorePress))
        #bs.widget(edit=self._seeMoreButton,showBufferBottom=100,upWidget=self._proMultButton)
        
        # bs.widget(edit=self._seeMoreButton,showBufferBottom=100,upWidget=self._seasonPopupMenu.getButtonWidget())
        # bs.widget(edit=self._seasonPopupMenu.getButtonWidget(),upWidget=self._backButton)
        # bs.widget(edit=self._backButton,downWidget=self._powerRankingAchievementsButton,rightWidget=self._seasonPopupMenu.getButtonWidget())

    def _onMorePress(self):
        if not self._canDoMoreButton:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('unavailableText'),color=(1,0,0))
            return
        seasonStr = '' if self._season is None else '&season='+('all_time' if self._season == 'a' else self._season)
        if self._leagueURLArg != '': leagueStr = '&league='+self._leagueURLArg
        else: leagueStr = ''
        bs.openURL(bsInternal._getServerAddress()+'/highscores?list=powerRankings&v=2'+leagueStr+seasonStr,aa='player')
        
    def _updateForPowerRankingInfo(self,data):

        if not self._rootWidget.exists(): return
        
        inTop = True if (data is not None and data['rank'] is not None) else False
        
        eqText = self._R.powerRankingPointsEqualsText
        ptsText = self._R.powerRankingPointsText
        numText = bs.getResource('numberText')

        doPercent = False
        finishedSeasonUnranked = False
        self._canDoMoreButton = True
        if bsInternal._getAccountState() != 'SIGNED_IN': statusText = '('+bs.getResource('notSignedInText')+')'
        elif inTop: statusText = numText.replace('${NUMBER}',str(data['rank']))
        elif data is not None:
            try:
                # print 'hAVE',len(data['scores'])
                # handle old seasons where we didn't wind up ranked at the end..
                if len(data['scores']) == 0:
                    statusText = self._R.powerRankingFinishedSeasonUnrankedText
                    extraText = ''
                    finishedSeasonUnranked = True
                    self._canDoMoreButton = False
                else:
                    ourPoints = _getPowerRankingPoints(data)
                    # progress = 0.0 if len(data['scores']) == 0 else float(ourPoints)/max(1,data['scores'][-1][1])
                    progress = float(ourPoints)/max(1,data['scores'][-1][1])
                    statusText = str(int(progress*100.0))+'%'
                    # extraText = '' if len(data['scores']) == 0 else '\n'+self._R.powerRankingPointsToRankedText.replace('${CURRENT}',str(ourPoints)).replace('${REMAINING}',str(data['scores'][-1][1]))
                    extraText = '\n'+self._R.powerRankingPointsToRankedText.replace('${CURRENT}',str(ourPoints)).replace('${REMAINING}',str(data['scores'][-1][1]))
                    doPercent = True
            except Exception:
                bs.printException('error updating power ranking')
                statusText = self._R.powerRankingNotInTopText.replace('${NUMBER}',str(data['listSize']))
                extraText = ''
        else: statusText = '-'

        #print 'UPDATING FOR SEASON',(data['s'] if data is not None else None)
        self._season = data['s'] if data is not None else None
        #print 'UPDATING FOR SEASON',self._season
        
        v = self._subContainerHeight - 20
        popupWasSelected = False
        if self._seasonPopupMenu is not None:
            b = self._seasonPopupMenu.getButtonWidget()
            if self._subContainer.getSelectedChild() == b: popupWasSelected = True
            b.delete()
        seasonChoices = []
        seasonChoicesDisplay = []
        seasonText = bs.getResource('league.seasonText')
        didFirst = False
        self._isCurrentSeason = False
        if data is not None:
            # build our list of seasons we have available
            for s in data['sl']:
                seasonChoices.append(s)
                if s != 'a' and not didFirst:
                    seasonChoicesDisplay.append(bs.getResource('league.currentSeasonText').replace('${NUMBER}',s))
                    didFirst = True
                    # if we either did not specify a season or specified the first, we're looking at the current..
                    if self._season in[s,None]:
                        self._isCurrentSeason = True
                elif s == 'a':
                    seasonChoicesDisplay.append(bs.getResource('league.allTimeText'))
                else:
                    seasonChoicesDisplay.append(seasonText.replace('${NUMBER}',s))
            self._seasonPopupMenu = PopupMenu(parent=self._subContainer,position=(390,v-45),width=150,buttonSize=(200,50),
                                              choices=seasonChoices,
                                              # choices=['Current Season (2)','Season 1',
                                              #          'Season A','Season B','Season C','Season D','Season E','Season F','Season G','All Time'],
                                              onValueChangeCall=bs.WeakCall(self._onSeasonChange),
                                              #choicesDisplay=[bs.getResource(a) for a in ['randomText','playModes.teamsText','playModes.freeForAllText']],
                                              choicesDisplay=seasonChoicesDisplay,
                                              currentChoice=self._season)
            if popupWasSelected: bs.containerWidget(edit=self._subContainer,selectedChild=self._seasonPopupMenu.getButtonWidget())
            #bs.widget(edit=self._seeMoreButton,showBufferBottom=100,upWidget=self._seasonPopupMenu.getButtonWidget())
            bs.widget(edit=self._seeMoreButton,showBufferBottom=100)
            bs.widget(edit=self._seasonPopupMenu.getButtonWidget(),upWidget=self._backButton)
            bs.widget(edit=self._backButton,downWidget=self._powerRankingAchievementsButton,rightWidget=self._seasonPopupMenu.getButtonWidget())

        #print 'IS CURRENT?',isCurrentSeason
            
        bs.textWidget(edit=self._leagueTitleText,text='' if self._season == 'a' else bs.getResource('league.leagueText'))
        
        if data is None:
            lName = ''
            lNum = ''
            lColor = (1,1,1)
            self._leagueURLArg = ''
        elif self._season == 'a':
            lName = bs.getResource('league.allTimeText')
            lNum = ''
            lColor = (1,1,1)
            self._leagueURLArg = ''
        else:
            lNum = ('['+str(data['l']['i'])+']') if data['l']['i2'] else ''
            #lName = bs.translate('leagueNames',data['l']['n'])+((' ('+str(data['l']['i'])+')') if data['l']['i2'] else '')
            lName = bs.translate('leagueNames',data['l']['n'])
            lColor = data['l']['c']
            self._leagueURLArg = (data['l']['n']+'_'+str(data['l']['i'])).lower()

        if data is None or self._season == 'a' or data['se'] is None:
            daysToEnd = 0
            minutesToEnd = 0
            toEndString = ''
            showSeasonEnd = False
        else:
            showSeasonEnd = True
            daysToEnd = data['se'][0]
            minutesToEnd = data['se'][1]
            if daysToEnd > 0: toEndString = bs.getResource('league.seasonEndsDaysText').replace('${NUMBER}',str(daysToEnd))
            elif daysToEnd == 0 and minutesToEnd >= 60: toEndString = bs.getResource('league.seasonEndsHoursText').replace('${NUMBER}',str(minutesToEnd/60))
            elif daysToEnd == 0 and minutesToEnd >= 0: toEndString = bs.getResource('league.seasonEndsMinutesText').replace('${NUMBER}',str(minutesToEnd))
            else: toEndString = bs.getResource('league.seasonEndedDaysAgoText').replace('${NUMBER}',str(-(daysToEnd+1)))
            
        bs.textWidget(edit=self._seasonEndsText,text=toEndString)
        bs.textWidget(edit=self._trophyCountsResetText,text=bs.getResource('league.trophyCountsResetText') if self._isCurrentSeason and showSeasonEnd else '')
        
        bs.textWidget(edit=self._leagueText,text=lName,color=lColor)
        lTextWidth = min(self._leagueTextMaxWidth,bs.getStringWidth(lName)*self._leagueTextScale)
        bs.textWidget(edit=self._leagueNumberText,text=lNum,color=lColor,
                      position=(self._leagueNumberBasePos[0]+lTextWidth*0.5+8,self._leagueNumberBasePos[1]+10))
        
        bs.textWidget(edit=self._toRankedText,
                      text=bs.getResource('coopSelectWindow.toRankedText')+''+extraText if doPercent else '')

        bs.textWidget(edit=self._yourPowerRankingText,
                      text=bs.getResource('rankText',fallback='coopSelectWindow.yourPowerRankingText') if (not doPercent) else '')
        
        bs.textWidget(edit=self._powerRankingRankText,
                      position=(473,v-70-(170 if doPercent else 220)),
                      text=statusText,big=True if (inTop or doPercent) else False,
                      scale=3.0 if (inTop or doPercent) else 0.7 if finishedSeasonUnranked else 1.0)

        if data is None or data['act'] is None:
            bs.buttonWidget(edit=self._activityMultButton,textColor=(0.7,0.7,0.8,0.5),iconColor=(0.5,0,0.5,0.3))
            bs.textWidget(edit=self._activityMultText,text='     -')
        else:
            bs.buttonWidget(edit=self._activityMultButton,textColor=(0.7,0.7,0.8,1.0),iconColor=(0.5,0,0.5,1.0))
            bs.textWidget(edit=self._activityMultText,text='x '+('%.2f' % data['act']))

        #havePro = bsUtils._havePro()
        havePro = False if data is None else data['p']
        proMult = 1.0 + float(bsInternal._getAccountMiscReadVal('proPowerRankingBoost',0.0))*0.01
        bs.textWidget(edit=self._proMultText,text='     -' if (data is None or not havePro) else 'x '+('%.2f' % proMult))
        bs.buttonWidget(edit=self._proMultButton,
                        textColor=(0.7,0.7,0.8,(1.0 if havePro else 0.5)),
                        iconColor=(0.5, 0, 0.5) if havePro else (0.5, 0, 0.5, 0.2))
        bs.buttonWidget(edit=self._powerRankingAchievementsButton,label=('' if data is None else (str(data['a'])+' '))+bs.getResource('achievementsText'))

        # for the achievement value, use the number they gave us for non-current seasons; otherwise calc our own
        totalAchValue = 0
        for ach in bsAchievement.gAchievements:
            if ach.isComplete(): totalAchValue += ach.getPowerRankingValue()
        if self._season != 'a' and not self._isCurrentSeason:
            if data is not None and 'at' in data: totalAchValue = data['at']
            
        bs.textWidget(edit=self._powerRankingAchievementTotalText,text='-' if data is None else ('+ '+ptsText.replace('${NUMBER}',str(totalAchValue))))

        totalTrophiesCount = _getPowerRankingPoints(data,'trophyCount')
        totalTrophiesValue = _getPowerRankingPoints(data,'trophies')
        bs.buttonWidget(edit=self._powerRankingTrophiesButton,label=('' if data is None else (str(totalTrophiesCount)+' '))+bs.getResource('trophiesText'))
        bs.textWidget(edit=self._powerRankingTrophiesTotalText,text='-' if data is None else ('+ '+ptsText.replace('${NUMBER}',str(totalTrophiesValue))))
        
        
        bs.textWidget(edit=self._powerRankingTotalText,text='-' if data is None else eqText.replace('${NUMBER}',str(_getPowerRankingPoints(data))))
        for w in self._powerRankingScoreWidgets: w.delete()
        self._powerRankingScoreWidgets = []

        scores = data['scores'] if data is not None else []

        tallyColor = (0.5,0.6,0.8)
        wParent = self._subContainer
        v2 = self._powerRankingScoreV
        
        for s in scores:
            h2 = 680
            isUs = s[3]
            self._powerRankingScoreWidgets.append(bs.textWidget(parent=wParent,position=(h2-20,v2),size=(0,0),
                                                                color=(1,1,1) if isUs else (0.6,0.6,0.7),
                                                                maxWidth=40,flatness=1.0,shadow=0.0,
                                                                text=numText.replace('${NUMBER}',str(s[0])),hAlign='right',vAlign='center',scale=0.5))
            self._powerRankingScoreWidgets.append(bs.textWidget(parent=wParent,position=(h2+20,v2),size=(0,0),
                                                                color=(1,1,1) if isUs else tallyColor,
                                                                maxWidth=60,text=str(s[1]),flatness=1.0,shadow=0.0,
                                                                hAlign='center',vAlign='center',scale=0.7))
            t = bs.textWidget(parent=wParent,position=(h2+60,v2-(28*0.5)/0.9),size=(210/0.9,28),
                              color=(1,1,1) if isUs else (0.6,0.6,0.6),
                              maxWidth=210,flatness=1.0,shadow=0.0,
                              autoSelect=True,selectable=True,clickActivate=True,
                              text=s[2],hAlign='left',vAlign='center',scale=0.9)
            self._powerRankingScoreWidgets.append(t)
            bs.textWidget(edit=t,onActivateCall=bs.Call(self._showAccountInfo,s[4],t))
            bs.widget(edit=t,leftWidget=self._seasonPopupMenu.getButtonWidget())
            v2 -= 28
        
    def _showAccountInfo(self,accountID,textWidget):
        bs.playSound(bs.getSound('swish'))
        AccountInfoWindow(accountID=accountID,
                          position=textWidget.getScreenSpaceCenter())
        
        
    def _onSeasonChange(self,value):
        #print 'SEASON CHANGED TO',value
        self._requestedSeason = value
        self._lastPowerRankingQueryTime = None # make sure we update asap
        self._update(show=True)
        
    def _saveState(self):
        pass
    
    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if not self._modal:
            uiGlobals['mainMenuWindow'] = CoopWindow(transition='inLeft').getRootWidget()
        
class CoopWindow(Window):

    def _updateCornerButtonPositions(self):
        offs = -55 if gSmallUI and bsInternal._isPartyIconVisible() else 0
        self._powerRankingButtonInstance.setPosition((self._width-282+offs,self._height-85-(4 if gSmallUI else 0)))
        self._storeButtonInstance.setPosition((self._width-170+offs,self._height-85-(4 if gSmallUI else 0)))

    def __init__(self,transition='inRight',originWidget=None):

        bsInternal._setAnalyticsScreen('Coop Window')
        
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        # try to recreate the same number of buttons we had last time so our re-selection code works
        try: self._tournamentButtonCount = bs.getConfig()['Tournament Rows']
        except Exception: self._tournamentButtonCount = 0

        #self._enableChallenges = True
        self._enableChallenges = False
        
        # same for challenges..
        try: self._challengeButtonCount = bs.getConfig()['Challenge Button Count']
        except Exception: self._challengeButtonCount = 0

        self._width = 1120
        self._height = 657 if gSmallUI else 730 if gMedUI else 800
        global gMainWindow
        gMainWindow = "Coop Select"
        self._R = R = bs.getResource('coopSelectWindow')
        topExtra = 20 if gSmallUI else 0

        self._tourneyDataUpToDate = False
        
        self._campaignDifficulty = bsInternal._getAccountMiscVal('campaignDifficulty','easy')
        
        bs.gCreateGameType = None
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),
                                              scaleOriginStackOffset=scaleOrigin,
                                              stackOffset=(0,-15) if gSmallUI else (0,7) if gMedUI else (0,0),transition=transition,
                                              scale = 1.2 if gSmallUI else 0.91 if gMedUI else 0.8)
        self._backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(75,self._height-87-(4 if gSmallUI else 0)),size=(120,60),scale=1.2,
                                               autoSelect=True,label=bs.getResource('backText'),buttonType='back')

        prb = self._powerRankingButtonInstance = PowerRankingButton(parent=self._rootWidget,position=(self._width-282,self._height-85-(4 if gSmallUI else 0)),size=(100,60),
                                                                    color=(0.4,0.4,0.9),
                                                                    textColor=(0.9,0.9,2.0),
                                                                    scale=1.05,onActivateCall=bs.WeakCall(self._switchToPowerRankings))
        self._powerRankingButton = prb.getButtonWidget()
        
        sb = self._storeButtonInstance = StoreButton(parent=self._rootWidget,position=(self._width-170,self._height-85-(4 if gSmallUI else 0)),size=(100,60),
                                                     color=(0.6,0.4,0.7),showTickets=True,buttonType='square',
                                                     saleScale=0.85,
                                                     textColor=(0.9,0.7,1.0),
                                                     scale=1.05,onActivateCall=bs.WeakCall(self._switchToStore,showTab=None))
        self._storeButton = sb.getButtonWidget()
        bs.widget(edit=self._backButton,rightWidget=self._powerRankingButton)
        bs.widget(edit=self._powerRankingButton,leftWidget=self._backButton)

        # move our corner buttons dynamically to keep them out of the way of the party icon :-(
        self._updateCornerButtonPositions()
        self._updateCornerButtonPositionsTimer = bs.Timer(1000,bs.WeakCall(self._updateCornerButtonPositions),repeat=True,timeType='real')
        
        self._lastTournamentQueryTime = None
        self._lastTournamentQueryResponseTime = None
        self._doingTournamentQuery = False

        bsConfig = bs.getConfig()
        
        try: self._selectedCampaignLevel = bsConfig['Selected Coop Campaign Level']
        except Exception: self._selectedCampaignLevel = None

        try: self._selectedCustomLevel = bsConfig['Selected Coop Custom Level']
        except Exception: self._selectedCustomLevel = None

        try: self._selectedChallengeLevel = bsConfig['Selected Coop Challenge Level']
        except Exception: self._selectedChallengeLevel = None
        
        self._doSelectionCallbacks = False # dont want initial construction affecting our last-selected
        v = self._height - 95
        t = campaignText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,v+40 - (0 if gSmallUI else 0)),size=(0,0),
                                         text=bs.getResource('playModes.singlePlayerCoopText',fallback='playModes.coopText'),
                                         hAlign="center",color=gTitleColor,scale=1.5,maxWidth=500,
                                         vAlign="center")
        campaignTextV = v

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,50),position=(75,self._height-87-(4 if gSmallUI else 0)+6),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(167,v+42 - (4 if gSmallUI else 0)))


        try: self._selectedRow = bsConfig['Selected Coop Row']
        except Exception: self._selectedRow = None
        
        self._starTex = bs.getTexture('star')
        self._lsbt = bs.getModel('levelSelectButtonTransparent')
        self._lsbo = bs.getModel('levelSelectButtonOpaque')
        self._aOutlineTex = bs.getTexture('achievementOutline')
        self._aOutlineModel = bs.getModel('achievementOutline')

        self._scrollWidth = self._width-130
        self._scrollHeight = self._height-160

        self._subContainerWidth = 800
        self._subContainerHeight = 1400

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,highlight=False,position=(65,70),size=(self._scrollWidth,self._scrollHeight),simpleCullingV=10.0)
        self._subContainer = None

        # take note of our account state; we'll refresh later if this changes
        self._accountStateNum = bsInternal._getAccountStateNum()
        # same for fg/bg state..
        self._fgState = bsUtils.gAppFGState
        
        self._refresh()
        self._restoreState()

        # even though we might display cached tournament data immediately, we don't consider it valid until we've pinged
        # the server for an update
        self._tourneyDataUpToDate = False
        
        # if we've got a cached tournament list for our account and info for each one of those tournaments,
        # go ahead and display it as a starting point...
        if (gAccountTournamentList is not None and gAccountTournamentList[0] == bsInternal._getAccountStateNum()
            and gAccountChallengeList is not None and gAccountChallengeList['accountState'] == bsInternal._getAccountStateNum()
            and all([tID in gTournamentInfo for tID in gAccountTournamentList[1]])):
            tourneyData = [gTournamentInfo[tID] for tID in gAccountTournamentList[1]]
            self._updateForData(tourneyData,gAccountChallengeList['challenges'])
            
        # this will pull new data periodically, update timers, etc..
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._update()
        
        
    def _update(self):
        
        curTime = bs.getRealTime()

        # if its been a while since we got a tournament update, consider the data invalid
        # (prevents us from joining tournaments if our internet connection goes down for a while)
        if self._lastTournamentQueryResponseTime is None or bs.getRealTime() - self._lastTournamentQueryResponseTime > 1000*60*2:
            self._tourneyDataUpToDate = False
            
        # if our account state has changed, do a full request
        accountStateNum = bsInternal._getAccountStateNum()
        if accountStateNum != self._accountStateNum:
            self._accountStateNum = accountStateNum
            self._saveState()
            self._refresh()
            # also encourage a new tournament query since this will clear out our current results..
            if not self._doingTournamentQuery: self._lastTournamentQueryTime = None

        # if we've been backgrounded/foregrounded, invalidate our tournament entries
        # (they will be refreshed below asap)
        if self._fgState != bsUtils.gAppFGState:
            self._tourneyDataUpToDate = False
            
        # send off a new tournament query if its been long enough or whatnot..
        if not self._doingTournamentQuery and (self._lastTournamentQueryTime is None
                                               or curTime-self._lastTournamentQueryTime > 30000
                                               or self._fgState != bsUtils.gAppFGState):
            self._fgState = bsUtils.gAppFGState
            self._lastTournamentQueryTime = curTime
            self._doingTournamentQuery = True
            bsInternal._tournamentQuery(args={'source':'coop window refresh','numScores':1},
                                        callback=bs.WeakCall(self._onTournamentQueryResponse))

        # decrement time on our tournament buttons..
        adsEnabled = bsInternal._haveIncentivizedAd()
        for tb in self._tournamentButtons:
            tb['timeRemaining'] = max(0,tb['timeRemaining']-1)
            if tb['timeRemainingValueText'] is not None:
                bs.textWidget(edit=tb['timeRemainingValueText'],
                              text=bsUtils.getTimeString(tb['timeRemaining']*1000,centi=False) if (tb['hasTimeRemaining'] and self._tourneyDataUpToDate) else '-')
            # also adjust the ad icon visibility
            if tb.get('allowAds',False) and bsInternal._hasVideoAds():
                bs.imageWidget(edit=tb['entryFeeAdImage'],opacity=1.0 if adsEnabled else 0.25)
                bs.textWidget(edit=tb['entryFeeTextRemaining'],color=(0.6,0.6,0.6,1 if adsEnabled else 0.2))
                
        

                
    def _updateForData(self,data,challengeData):

        # if the number of tournaments or challenges in the data differs from our current arrangement, refresh with
        # the new number
        if ((data is None and (self._tournamentButtonCount != 0 or self._challengeButtonCount != 0))
            or (data is not None and ((len(data) != self._tournamentButtonCount) or len(challengeData) != self._challengeButtonCount))):
            self._tournamentButtonCount = len(data) if data is not None else 0
            self._challengeButtonCount = len(challengeData) if challengeData is not None else 0
            bs.getConfig()['Tournament Rows'] = self._tournamentButtonCount
            bs.getConfig()['Challenge Button Count'] = self._challengeButtonCount
            self._refresh()

        # push new data to our challenge buttons
        if self._enableChallenges:
            for i,cb in enumerate(self._challengeButtons):
                try: cb.updateForData(None if challengeData is None else challengeData[i])
                except Exception,e: print 'EXC updating challenge button',e
                
        # update all of our tourney buttons based on whats in data..
        for i,tb in enumerate(self._tournamentButtons):
            
            try: entry = data[i]
            except Exception: entry = None
            prizeYOffs = 0 if entry is None else 34 if 'prizeRange3' in entry else 20 if 'prizeRange2' in entry else 12
            xOffs = 90

            pr1,pv1,pr2,pv2,pr3,pv3 = _getPrizeStrings(entry)
            enabled = False if 'requiredLeague' in entry else True
            bs.buttonWidget(edit=tb['button'],color=(0.5,0.7,0.2) if enabled else (0.5,0.5,0.5))
            bs.imageWidget(edit=tb['lockImage'],opacity=0.0 if enabled else 1.0)
            bs.textWidget(edit=tb['prizeRange1Text'],
                          text='-' if pr1 == '' else pr1,
                          position=(tb['buttonX']+365+xOffs,
                                    tb['buttonY']+tb['buttonScaleY']-93+prizeYOffs))

            # we want to draw values containing tickets a bit smaller
            # (scratch that; we now draw medals a bit bigger)
            ticketChar = bs.getSpecialChar('ticketBacking')
            prizeValueScaleLarge = 1.0
            prizeValueScaleSmall = 1.0
            
            bs.textWidget(edit=tb['prizeValue1Text'],
                          text='-' if pv1 == '' else pv1,
                          scale=prizeValueScaleLarge if ticketChar not in pv1 else prizeValueScaleSmall,
                          position=(tb['buttonX']+380+xOffs,tb['buttonY']+tb['buttonScaleY']-93+prizeYOffs))

            bs.textWidget(edit=tb['prizeRange2Text'],
                          text=pr2,
                          position=(tb['buttonX']+365+xOffs,
                                    tb['buttonY']+tb['buttonScaleY']-93-45+prizeYOffs))
            bs.textWidget(edit=tb['prizeValue2Text'],
                          text=pv2,
                          scale=prizeValueScaleLarge if ticketChar not in pv2 else prizeValueScaleSmall,
                          position=(tb['buttonX']+380+xOffs,tb['buttonY']+tb['buttonScaleY']-93-45+prizeYOffs))

            bs.textWidget(edit=tb['prizeRange3Text'],
                          text=pr3,
                          position=(tb['buttonX']+365+xOffs,
                                    tb['buttonY']+tb['buttonScaleY']-93-90+prizeYOffs))
            bs.textWidget(edit=tb['prizeValue3Text'],
                          text=pv3,
                          scale=prizeValueScaleLarge if ticketChar not in pv3 else prizeValueScaleSmall,
                          position=(tb['buttonX']+380+xOffs,tb['buttonY']+tb['buttonScaleY']-93-90+prizeYOffs))

            leaderName = '-'
            leaderScore = '-'
            if entry is not None and entry['scores']:
                score = tb['leader'] = copy.deepcopy(entry['scores'][0])
                leaderName = score[1]
                leaderScore = bsUtils.getTimeString(score[0]*10,centi=True) if entry['scoreType'] == 'time' else str(score[0])
            else:
                tb['leader'] = None
                
            bs.textWidget(edit=tb['currentLeaderNameText'],text=leaderName)
            self._tournamentLeaderScoreType = None if entry is None else entry['scoreType']
            bs.textWidget(edit=tb['currentLeaderScoreText'],text=leaderScore)
            bs.buttonWidget(edit=tb['moreScoresButton'],label='-' if entry is None else self._R.seeMoreText)
            outOfTimeText = u'-' if entry is None or 'totalTime' not in entry else bs.uni(self._R.ofTotalTimeText).replace(u'${TOTAL}',bsUtils.getTimeString(entry['totalTime']*1000,centi=False))
            bs.textWidget(edit=tb['timeRemainingOutOfText'],text=outOfTimeText)
            
            tb['timeRemaining'] = 0 if entry is None else entry['timeRemaining']
            tb['hasTimeRemaining'] = False if entry is None else True
            tb['tournamentID'] = None if entry is None else entry['tournamentID']
            tb['requiredLeague'] = None if 'requiredLeague' not in entry else entry['requiredLeague']

            game = None if entry is None else gTournamentInfo[tb['tournamentID']]['game']

            if game is None:
                bs.textWidget(edit=tb['buttonText'],text='-')
                bs.imageWidget(edit=tb['image'],texture=bs.getTexture('black'),opacity=0.2)
            else:
                campaignName,levelName = game.split(':')
                campaign = bsCoopGame.getCampaign(campaignName)
                maxPlayers = gTournamentInfo[tb['tournamentID']]['maxPlayers']
                t = campaign.getLevel(levelName).getDisplayNameLocalized()+' '+bs.getResource('playerCountAbbreviatedText').replace('${COUNT}',str(maxPlayers))
                bs.textWidget(edit=tb['buttonText'],text=t)
                bs.imageWidget(edit=tb['image'],texture=campaign.getLevel(levelName).getPreviewTex(),opacity=1.0 if enabled else 0.5)

            fee = None if entry is None else entry['fee']

            if fee is None:
                feeVar = None
            elif fee == 4:
                feeVar = 'price.tournament_entry_4'
            elif fee == 3:
                feeVar = 'price.tournament_entry_3'
            elif fee == 2:
                feeVar = 'price.tournament_entry_2'
            elif fee == 1:
                feeVar = 'price.tournament_entry_1'
            else:
                if fee != 0: print 'Unknown fee value:',fee
                feeVar = 'price.tournament_entry_0'

            tb['allowAds'] = allowAds = entry['allowAds']

            finalFee = None if feeVar is None else bsInternal._getAccountMiscReadVal(feeVar,'?')
            
            finalFeeStr = '' if feeVar is None else bs.getResource('getTicketsWindow.freeText') if finalFee == 0 else (bs.getSpecialChar('ticketBacking')+str(finalFee))

            adTriesRemaining = gTournamentInfo[tb['tournamentID']]['adTriesRemaining']
            freeTriesRemaining = gTournamentInfo[tb['tournamentID']]['freeTriesRemaining']
            
            # now, if this fee allows ads and we support video ads, show the 'or ad' version
            if allowAds and bsInternal._hasVideoAds():
                adsEnabled = bsInternal._haveIncentivizedAd()
                bs.imageWidget(edit=tb['entryFeeAdImage'],opacity=1.0 if adsEnabled else 0.25)
                orText = bs.getResource('orText').replace('${A}','').replace('${B}','').strip()
                bs.textWidget(edit=tb['entryFeeTextOr'],text=orText)
                bs.textWidget(edit=tb['entryFeeTextTop'],position=(tb['buttonX']+360,tb['buttonY']+tb['buttonScaleY']-60),
                              scale=1.3,text=finalFeeStr)
                # possibly show number of ad-plays remaining
                bs.textWidget(edit=tb['entryFeeTextRemaining'],
                              position=(tb['buttonX']+360,tb['buttonY']+tb['buttonScaleY']-146),
                              text='' if adTriesRemaining in [None,0] else (''+str(adTriesRemaining)),
                              color=(0.6,0.6,0.6,1 if adsEnabled else 0.2))
            else:
                bs.imageWidget(edit=tb['entryFeeAdImage'],opacity=0.0)
                bs.textWidget(edit=tb['entryFeeTextOr'],text='')
                bs.textWidget(edit=tb['entryFeeTextTop'],position=(tb['buttonX']+360,tb['buttonY']+tb['buttonScaleY']-80),
                              scale=1.3,text=finalFeeStr)
                # possibly show number of free-plays remaining
                bs.textWidget(edit=tb['entryFeeTextRemaining'],
                              position=(tb['buttonX']+360,tb['buttonY']+tb['buttonScaleY']-100),
                              text='' if (freeTriesRemaining in [None,0] or finalFee != 0) else (''+str(freeTriesRemaining)),color=(0.6,0.6,0.6,1))
        
    def _onTournamentQueryResponse(self,data):

        if data is not None:
            challengeData = data['c']
            tournamentData = data['t'] # this used to be the whole payload
            self._lastTournamentQueryResponseTime = bs.getRealTime()
        else:
            challengeData = tournamentData = None
            
        # keep our cached tourney info up to date
        if data is not None:
            self._tourneyDataUpToDate = True
            _cacheTournamentInfo(tournamentData)
            # also cache the current tourney list/order for this account
            global gAccountTournamentList
            gAccountTournamentList = (bsInternal._getAccountStateNum(),[e['tournamentID'] for e in tournamentData])
            # and cache the current challenge list for this account
            global gAccountChallengeList
            # challenge times are provided relative to now; convert them to absolute times
            # so they stay correct as time marches on
            challengeData = copy.deepcopy(challengeData)
            t = time.time()
            for c in challengeData:
                for key in ['waitStart','waitEnd','start','end']:
                    c[key] += t
            gAccountChallengeList = {'accountState':bsInternal._getAccountStateNum(),
                                     'challenges':challengeData}
            
        self._doingTournamentQuery = False

        self._updateForData(tournamentData, challengeData)


    def _setCampaignDifficulty(self,difficulty):
        if difficulty != self._campaignDifficulty:
            bs.playSound(bs.getSound('gunCocking'))
            if difficulty not in ('easy','hard'):
                print 'ERROR: invalid campaign difficulty:',difficulty
                difficulty = 'easy'
            self._campaignDifficulty = difficulty
            
            bsInternal._addTransaction({'type':'SET_MISC_VAL','name':'campaignDifficulty','value':difficulty})
            self._refreshCampaignRow()
        else:
            bs.playSound(bs.getSound('click01'))
        
    def _refreshCampaignRow(self):

        parentWidget = self._campaignSubContainer
        
        # clear out anything in the parent widget already..
        for c in parentWidget.getChildren(): c.delete()

        if self._enableChallenges: nextWidgetDown = self._challengesInfoButton
        else: nextWidgetDown = self._tournamentInfoButton
            
        h = 0
        hBase = 6
        v2 = -2
        selColor = (0.75,0.85,0.5)
        selColorHard = (0.4,0.7,0.2)
        unSelColor = (0.5,0.5,0.5)
        selTextColor = (2,2,0.8)
        unSelTextColor = (0.6,0.6,0.6)
        self._easyButton = bs.buttonWidget(parent=parentWidget,position=(h+30,v2+105),size=(120,70),label=bs.getResource('difficultyEasyText'),
                                           buttonType='square',autoSelect=True,enableSound=False,onActivateCall=bs.Call(self._setCampaignDifficulty,'easy'),
                                           onSelectCall=bs.Call(self._selChange,'campaign','easyButton'),
                                           color=selColor if self._campaignDifficulty == 'easy' else unSelColor,
                                           textColor=selTextColor if self._campaignDifficulty == 'easy' else unSelTextColor)
        bs.widget(edit=self._easyButton,showBufferLeft=100)
        if self._selectedCampaignLevel == 'easyButton':
            bs.containerWidget(edit=parentWidget,selectedChild=self._easyButton,visibleChild=self._easyButton)

        self._hardButton = bs.buttonWidget(parent=parentWidget,position=(h+30,v2+32),size=(120,70),label=bs.getResource('difficultyHardText'),
                                           buttonType='square',autoSelect=True,enableSound=False,onActivateCall=bs.Call(self._setCampaignDifficulty,'hard'),
                                           onSelectCall=bs.Call(self._selChange,'campaign','hardButton'),
                                           color=selColorHard if self._campaignDifficulty == 'hard' else unSelColor,
                                           textColor=selTextColor if self._campaignDifficulty == 'hard' else unSelTextColor)
        bs.widget(edit=self._hardButton,showBufferLeft=100)
        if self._selectedCampaignLevel == 'hardButton':
            bs.containerWidget(edit=parentWidget,selectedChild=self._hardButton,visibleChild=self._hardButton)

        bs.widget(edit=self._hardButton,downWidget=nextWidgetDown)
            
        h = hBase

        hSpacing = 200
        campaignButtons = []

        if self._campaignDifficulty == 'easy': campaignName = 'Easy'
        else: campaignName = 'Default'
        
        items = [campaignName+':Onslaught Training',
                 campaignName+':Rookie Onslaught',
                 campaignName+':Rookie Football',
                 campaignName+':Pro Onslaught',
                 campaignName+':Pro Football',
                 campaignName+':Pro Runaround',
                 campaignName+':Uber Onslaught',
                 campaignName+':Uber Football',
                 campaignName+':Uber Runaround']
        
        items += [campaignName+':The Last Stand']

        if self._selectedCampaignLevel is None:
            self._selectedCampaignLevel = items[0]
            
        h = 150
        for i in items:
            isLastSel = (i==self._selectedCampaignLevel)
            campaignButtons.append(self._GameButton(self, parentWidget, i, h, v2, isLastSel, 'campaign').getButton())
            h += hSpacing

        bs.widget(edit=self._easyButton,upWidget=self._backButton)
            
        bs.widget(edit=campaignButtons[0],leftWidget=self._easyButton)
        for b in campaignButtons:
            bs.widget(edit=b,upWidget=self._backButton,downWidget=nextWidgetDown)

        # update our existing perecent-complete text..
        campaign = bsCoopGame.getCampaign(campaignName)
        levels = campaign.getLevels()
        levelsComplete = sum((1 if l.getComplete() else 0) for l in levels)

        # last level cant be completed; hence the -1
        progress = min(1.0,float(levelsComplete)/(len(levels)-1))
        pStr = str(int(progress*100.0))+'%'

        self._campaignPercentText = bs.textWidget(edit=self._campaignPercentText,
                                                  text=self._R.campaignText+' ('+pStr+')',)
            

    def _onChallengesInfoPress(self):
        txt = self._R.challengesInfoText
        ConfirmWindow(txt, cancelButton=False, width=550, height=260, originWidget=self._challengesInfoButton)
        
    def _onTournamentInfoPress(self):
        txt = self._R.tournamentInfoText
        ConfirmWindow(txt, cancelButton=False, width=550, height=260, originWidget=self._tournamentInfoButton)
        
    def _refresh(self):

        # (re)create the sub-container if need be..
        if self._subContainer is not None: self._subContainer.delete()

        tourneyRowHeight = 200
        self._subContainerHeight = 620+self._tournamentButtonCount*tourneyRowHeight + (250 if (self._challengeButtonCount > 0 and self._enableChallenges) else 120 if self._enableChallenges else 0)# - (250 if not self._enableChallenges else 0)
        
        self._subContainer = c = bs.containerWidget(parent=self._scrollWidget,size=(self._subContainerWidth,self._subContainerHeight),background=False)

        # so we can still select root level widgets with controllers
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=self._subContainer,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._backButton,selectedChild=self._scrollWidget)

        wParent = self._subContainer
        hBase = 6
        
        v = self._subContainerHeight - 73
        vSpacing = 190

        self._campaignPercentText = bs.textWidget(parent=wParent,position=(hBase+27,v+30),size=(0,0),
                                                  text='',hAlign="left",
                                                  vAlign='center',color=gTitleColor,scale=1.1)

        rowVShowBuffer = 100
        v -= 198

        h = hBase

        self._campaignHScroll = campaignHScroll = hScroll = bs.hScrollWidget(parent=wParent,size=(self._scrollWidth-10,205),position=(-5,v),simpleCullingH=70,
                                                                             highlight=False,borderOpacity=0.0,color=(0.45,0.4,0.5),onSelectCall=bs.Call(self._onRowSelected,'campaign'))
        bs.widget(edit=hScroll,showBufferTop=rowVShowBuffer,showBufferBottom=rowVShowBuffer,autoSelect=True)
        if self._selectedRow == 'campaign': bs.containerWidget(edit=wParent,selectedChild=hScroll,visibleChild=hScroll)
        bs.containerWidget(edit=hScroll,claimsLeftRight=True)
        self._campaignSubContainer = bs.containerWidget(parent=hScroll,size=(180+200*10,200),background=False)

        # Challenges
        if self._enableChallenges:
            self._challengeButtons = challengeButtons = []

            v2 = -2
            h = 0
            v -= 50
            txt = bs.getResource('coopSelectWindow.challengesText')
            tWidth = bs.getStringWidth(txt)
            bs.textWidget(parent=wParent,position=(hBase+27,v+30-200+198),size=(0,0),text=txt,
                          hAlign="left",vAlign='center',color=gTitleColor,scale=1.1)
            self._challengesInfoButton = bs.buttonWidget(parent=wParent,label='?',size=(20, 20),textScale=0.6,
                                                         position=(hBase+27+tWidth*1.1+15,v+18),buttonType='square',
                                                         color=(0.6, 0.5, 0.65), textColor=(0.7, 0.6, 0.75), autoSelect=True,
                                                         onActivateCall=self._onChallengesInfoPress)

            # say 'unavailable' if there are zero tournaments, and if we're not signed in add that as well (that's probably why we see no tournaments)
            if self._challengeButtonCount == 0:
                unavailableText = bs.getResource('unavailableText')
                if bsInternal._getAccountState() != 'SIGNED_IN':
                    unavailableText += ' ('+bs.getResource('notSignedInText')+')'
                bs.textWidget(parent=wParent,position=(hBase+47,v),size=(0,0),
                              text=unavailableText,hAlign="left",vAlign='center',color=gTitleColor,scale=0.9)
                v -= 40

            else:
                v -= 220
                items = ['Challenges:Ninja Fight'] * self._challengeButtonCount
                self._challengeHScroll = challengeHScroll = hScroll = bs.hScrollWidget(parent=wParent,size=(self._scrollWidth-10,225),position=(-5,v),highlight=False,
                                                           borderOpacity=0.0,color=(0.45,0.4,0.5),onSelectCall=bs.Call(self._onRowSelected,'challenges'))
                bs.widget(edit=self._challengesInfoButton,downWidget=self._challengeHScroll,rightWidget=self._challengesInfoButton)
                bs.widget(edit=hScroll,showBufferTop=rowVShowBuffer,showBufferBottom=1.5*rowVShowBuffer,autoSelect=True)
                if self._selectedRow == 'challenges': bs.containerWidget(edit=wParent,selectedChild=hScroll,visibleChild=hScroll)
                bs.containerWidget(edit=hScroll,claimsLeftRight=True)
                hSpacing = 300
                sc2 = bs.containerWidget(parent=hScroll,size=(max(self._scrollWidth-24,30+hSpacing*self._challengeButtonCount),200),background=False)
                h = 0
                v2 = -4
                for num,i in enumerate(items):
                    isLastSel = (num == self._selectedChallengeLevel)
                    self._challengeButtons.append(self._ChallengeButton(self, sc2, num, h, v2, isLastSel, 'challenges'))
                    h += hSpacing
        
        # Tournaments
            
        self._tournamentButtons = []

        v -= 53
        txt = bs.getResource('tournamentsText',fallback='tournamentText')
        tWidth = bs.getStringWidth(txt)
        bs.textWidget(parent=wParent,position=(hBase+27,v+30),size=(0,0),
                                     text=txt,hAlign="left",vAlign='center',color=gTitleColor,scale=1.1)
        self._tournamentInfoButton = bs.buttonWidget(parent=wParent,label='?',size=(20, 20),textScale=0.6,
                                                     position=(hBase+27+tWidth*1.1+15,v+18),buttonType='square',
                                                     color=(0.6, 0.5, 0.65), textColor=(0.7, 0.6, 0.75), autoSelect=True,
                                                     upWidget = ((self._challengeHScroll if self._challengeButtonCount > 0 else self._challengesInfoButton)
                                                                 if self._enableChallenges else self._campaignHScroll),
                                                     #upWidget = self._campaignHScroll,
                                                     onActivateCall=self._onTournamentInfoPress)
        bs.widget(edit=self._tournamentInfoButton,leftWidget=self._tournamentInfoButton,rightWidget=self._tournamentInfoButton)

        # say 'unavailable' if there are zero tournaments, and if we're not signed in add that as well (that's probably why we see no tournaments)
        if self._tournamentButtonCount == 0:
            unavailableText = bs.getResource('unavailableText')
            if bsInternal._getAccountState() != 'SIGNED_IN':
                unavailableText += ' ('+bs.getResource('notSignedInText')+')'
            bs.textWidget(parent=wParent,position=(hBase+47,v),size=(0,0),
                          text=unavailableText,hAlign="left",vAlign='center',color=gTitleColor,scale=0.9)
            v -= 40
        v -= 198
        
        if self._tournamentButtonCount > 0:
            
            for i in range(self._tournamentButtonCount):
                tournamentHScroll = hScroll = bs.hScrollWidget(parent=wParent,size=(self._scrollWidth-10,205),position=(-5,v),
                                                               highlight=False,borderOpacity=0.0,color=(0.45,0.4,0.5),
                                                               onSelectCall=bs.Call(self._onRowSelected,'tournament'+str(i+1)))
                bs.widget(edit=hScroll,showBufferTop=rowVShowBuffer,showBufferBottom=rowVShowBuffer,autoSelect=True)
                if self._selectedRow == 'tournament'+str(i+1): bs.containerWidget(edit=wParent,selectedChild=hScroll,visibleChild=hScroll)
                bs.containerWidget(edit=hScroll,claimsLeftRight=True)
                sc2 = bs.containerWidget(parent=hScroll,size=(self._scrollWidth-24,200),background=False)
                h = 0
                v2 = -2
                isLastSel = True
                self._tournamentButtons.append(self._tournamentButton(sc2,h,v2,isLastSel))
                v -= 200

        # Custom Games
        v2 = -2
        h = 0
        v -= 50
        bs.textWidget(parent=wParent,position=(hBase+27,v+30+198),size=(0,0),text=bs.getResource('practiceText',fallback='coopSelectWindow.customText'),
                      hAlign="left",vAlign='center',color=gTitleColor,scale=1.1)
        # bs.textWidget(parent=wParent,position=(hBase+27,v+30),size=(0,0),text=bs.getResource('coopSelectWindow.challengesText',fallback='coopSelectWindow.customText'),
        #               hAlign="left",vAlign='center',color=gTitleColor,scale=1.1)

        #v -= 198
        items = ['Challenges:Ninja Fight',
                 'Challenges:Pro Ninja Fight',
                 'Challenges:Meteor Shower',
                 'Challenges:Target Practice B',
                 'Challenges:Target Practice',
                 'Challenges:Infinite Onslaught',
                 'Challenges:Infinite Runaround',
                 #'Challenges:Lake Frigid Race',
                 # 'Challenges:Uber Runaround',
                 # 'Challenges:Runaround',
                 # 'Challenges:Pro Race',
                 # 'Challenges:Pro Football',
                 #'Challenges:Epic Meteor Shower',
                 #'Challenges:Testing',
                 #'User:Ninja Fight',
        ]
        # show easter-egg-hunt either if its easter or we own it
        if bsInternal._getAccountMiscReadVal('easter',False) or bsInternal._getPurchased('games.easter_egg_hunt'):
            items = ['Challenges:Easter Egg Hunt',
                     'Challenges:Pro Easter Egg Hunt'] + items
        
        # add all custom user levels here..
        items += ['User:'+l.getName() for l in bsCoopGame.getCampaign('User').getLevels()]
        
        self._customHScroll = customHScroll = hScroll = bs.hScrollWidget(parent=wParent,size=(self._scrollWidth-10,205),position=(-5,v),highlight=False,
                                                   borderOpacity=0.0,color=(0.45,0.4,0.5),onSelectCall=bs.Call(self._onRowSelected,'custom'))
        bs.widget(edit=hScroll,showBufferTop=rowVShowBuffer,showBufferBottom=1.5*rowVShowBuffer,autoSelect=True)
        if self._selectedRow == 'custom': bs.containerWidget(edit=wParent,selectedChild=hScroll,visibleChild=hScroll)
        bs.containerWidget(edit=hScroll,claimsLeftRight=True)
        sc2 = bs.containerWidget(parent=hScroll,size=(max(self._scrollWidth-24,30+200*len(items)),200),background=False)


        hSpacing = 200
        self._customButtons = customButtons = []
        h = 0
        v2 = -2
        for i in items:
            isLastSel = (i == self._selectedCustomLevel)
            self._customButtons.append(self._GameButton(self, sc2, i, h, v2, isLastSel, 'custom'))
            h += hSpacing

                
        # we cant fill in our campaign row until tourney buttons are in place.. (for wiring up)
        self._refreshCampaignRow()
        
        for i in range(len(self._tournamentButtons)):
            bs.widget(edit=self._tournamentButtons[i]['button'],upWidget=self._tournamentInfoButton if i == 0 else self._tournamentButtons[i-1]['button'],
                      downWidget=self._tournamentButtons[(i+1)]['button'] if i+1 < len(self._tournamentButtons) else customHScroll)
            bs.widget(edit=self._tournamentButtons[i]['moreScoresButton'],
                      downWidget=self._tournamentButtons[(i+1)]['currentLeaderNameText'] if i+1 < len(self._tournamentButtons) else customHScroll)
            bs.widget(edit=self._tournamentButtons[i]['currentLeaderNameText'],upWidget=self._tournamentInfoButton if i == 0 else self._tournamentButtons[i-1]['moreScoresButton'])

        for b in self._customButtons:
            try:
                bs.widget(edit=b.getButton(),upWidget=tournamentHScroll if self._tournamentButtons else self._tournamentInfoButton)
            except Exception:
                bs.printException('Error wiring up custom buttons')
            # bs.widget(edit=b.getButton(),upWidget=campaignHScroll,
            #           downWidget=self._tournamentButtons[0]['button'] if self._tournamentButtons else None)

        if self._enableChallenges:
            for b in self._challengeButtons:
                try:
                    bs.widget(edit=b.getButton(),upWidget=self._challengesInfoButton, downWidget=self._tournamentInfoButton)
                except Exception:
                    bs.printException('Error wiring up challenge buttons')

        bs.buttonWidget(edit=self._backButton,onActivateCall=self._back)
        # theres probably several 'onSelected' callbacks pushed onto the
        # event queue.. we need to push ours too so we're enabled *after* them
        bs.pushCall(self._enableSelectableCallback)

    def _onRowSelected(self,row):
        if self._doSelectionCallbacks:
            if self._selectedRow != row:
                self._selectedRow = row
    
    def _enableSelectableCallback(self):
        self._doSelectionCallbacks = True

    class _GameButton(object):

            
        def __init__(self, window, parent, game, x, y, select, row):

            self._game = game
            sx = 195.0
            sy = 195.0

            campaignName,levelName = game.split(':')

            # hack - The Last Stand doesn't actually exist in the easy tourney..
            # we just want it for display purposes.. map it to the hard-mode version.
            if game == 'Easy:The Last Stand':
                campaignName = 'Default'

            campaign = bsCoopGame.getCampaign(campaignName)

            # levels = campaign.getLevels()
            rating = campaign.getLevel(levelName).getRating()

            if game == 'Easy:The Last Stand': rating = None

            if rating is None or rating == 0.0: stars = 0
            elif rating >= 9.5: stars = 3
            elif rating >= 7.5: stars = 2
            else: stars = 1

            # if this campaign is sequential, make sure we've unlockedd the one before this
            # unlocked = True
            # if campaign.isSequential():
            #     for l in levels:
            #         if l.getName() == levelName:
            #             break
            #         if not l.getComplete():
            #             unlocked = False
            #             break

            # we never actually allow playing last-stand on easy mode..
            # if game == 'Easy:The Last Stand':
            #     unlocked = False

            # hard-code games we havn't unlocked..
            # if ((game in ('Challenges:Infinite Runaround','Challenges:Infinite Onslaught') and not bsUtils._havePro())
            #     or (game in ('Challenges:Meteor Shower',) and not bsInternal._getPurchased('games.meteor_shower'))
            #     or (game in ('Challenges:Target Practice','Challenges:Target Practice B') and not bsInternal._getPurchased('games.target_practice'))
            #     or (game in ('Challenges:Ninja Fight',) and not bsInternal._getPurchased('games.ninja_fight'))
            #     or (game in ('Challenges:Pro Ninja Fight',) and not bsInternal._getPurchased('games.ninja_fight'))):
            #     unlocked = False

            # hard-coding availability for tournament
            # if row in ['tournament1','tournament2','tournament3']: unlocked = True

            # lets tint levels a slightly different color when easy mode is selected..
            #unlockedColor = (0.85,0.95,0.5) if game.startswith('Easy:') else None

            self._button = b = bs.buttonWidget(parent=parent,position=(x+23,y+4),size=(sx,sy),label='',
                                                   onActivateCall=bs.Call(window._run,game),
                                                   #color=unlockedColor if unlocked else (0.5,0.5,0.5),
                                                   buttonType='square',autoSelect=True,
                                                   onSelectCall=bs.Call(window._selChange,row,game))
            bs.widget(edit=b,showBufferBottom=50,showBufferTop=50,showBufferLeft=400,showBufferRight=200)
            if select:
                bs.containerWidget(edit=parent,selectedChild=b,visibleChild=b)
            imageWidth = sx*0.85*0.75
            self._previewWidget = bs.imageWidget(parent=parent,drawController=b,position=(x+21+sx*0.5-imageWidth*0.5,y+sy-104),
                                                 size=(imageWidth,imageWidth*0.5),
                                                 modelTransparent=window._lsbt,modelOpaque=window._lsbo,
                                                 texture=campaign.getLevel(levelName).getPreviewTex(),
                                                 # opacity=1.0 if unlocked else 0.3,
                                                 maskTexture=bs.getTexture('mapPreviewMask'))

            translated = campaign.getLevel(levelName).getDisplayNameLocalized()
            self._achievements = bsAchievement.getAchievementsForCoopLevel(game)

            self._nameWidget = bs.textWidget(parent=parent,drawController=b,position=(x+20+sx*0.5,y+sy-27),
                                             size=(0,0),hAlign='center',text=translated,
                                             vAlign='center',
                                             maxWidth=sx*0.76,
                                             scale=0.85)
                                             #color=(0.8,1.0,0.8,1.0) if unlocked else (0.7,0.7,0.7,0.7))
            xs = x+(67 if self._achievements else 50)
            ys = y+sy-(137 if self._achievements else 157)

            starScale = 35.0 if self._achievements else 45.0

            self._starWidgets = []
            for i in range(stars):
                w = bs.imageWidget(parent=parent,drawController=b,position=(xs,ys),size=(starScale,starScale),
                                   #color=(2.2,1.2,0.3) if unlocked else (1,1,1),
                                   texture=window._starTex)
                                   #opacity=1.0 if unlocked else 0.3)
                self._starWidgets.append(w)
                xs += starScale
            for i in range(3-stars):
                bs.imageWidget(parent=parent,drawController=b,position=(xs,ys),size=(starScale,starScale),
                               color=(0,0,0),
                               texture=window._starTex,opacity=0.3)
                xs += starScale

            xa = x+69
            ya = y+sy-168
            aScale = 30.0
            self._achievementWidgets = []
            for a in self._achievements:
                aComplete = a.isComplete()
                w = bs.imageWidget(parent=parent,drawController=b,position=(xa,ya),size=(aScale,aScale),
                                   color=tuple(a.getIconColor(aComplete)[:3]) if aComplete else (1.2,1.2,1.2),
                                   texture=a.getIconTexture(aComplete))
                                   #opacity=1.0 if (aComplete and unlocked) else 0.3)
                w2 = bs.imageWidget(parent=parent,drawController=b,position=(xa,ya),size=(aScale,aScale),
                                    color=(2,1.4,0.4),
                                    #opacity=1.0 if unlocked else 0.2,
                                    texture=window._aOutlineTex,
                                    modelTransparent=window._aOutlineModel)
                self._achievementWidgets.append([w,w2])
                # if aComplete:
                xa += aScale*1.2

            #if not unlocked:
            self._lockWidget = bs.imageWidget(parent=parent,drawController=b,position=(x-8+sx*0.5,y+sy*0.5-20),size=(60,60),
                                              opacity=0.0, texture=bs.getTexture('lock'))

            # give a quasi-random update increment to spread the load..
            self._updateTimer = bs.Timer(900+random.randrange(200), bs.WeakCall(self._update),repeat=True,timeType='real')
            self._update()

        def getButton(self):
            return self._button

        def _update(self):

            game = self._game
            campaignName,levelName = game.split(':')
            
            # update locked state
            unlocked = True
            
            # hack - The Last Stand doesn't actually exist in the easy tourney..
            # we just want it for display purposes.. map it to the hard-mode version.
            if game == 'Easy:The Last Stand':
                campaignName = 'Default'
                
            campaign = bsCoopGame.getCampaign(campaignName)

            levels = campaign.getLevels()

            # if this campaign is sequential, make sure we've unlocked everything up to here
            unlocked = True
            if campaign.isSequential():
                for l in levels:
                    if l.getName() == levelName:
                        break
                    if not l.getComplete():
                        unlocked = False
                        break

            # we never actually allow playing last-stand on easy mode..
            if game == 'Easy:The Last Stand':
                unlocked = False

            # if random.random() < 0.5: unlocked = True
            # else: unlocked = False
            
            # hard-code games we havn't unlocked..
            if ((game in ('Challenges:Infinite Runaround','Challenges:Infinite Onslaught') and not bsUtils._havePro())
                or (game in ('Challenges:Meteor Shower',) and not bsInternal._getPurchased('games.meteor_shower'))
                or (game in ('Challenges:Target Practice','Challenges:Target Practice B') and not bsInternal._getPurchased('games.target_practice'))
                or (game in ('Challenges:Ninja Fight',) and not bsInternal._getPurchased('games.ninja_fight'))
                or (game in ('Challenges:Pro Ninja Fight',) and not bsInternal._getPurchased('games.ninja_fight'))
                or (game in ('Challenges:Easter Egg Hunt','Challenges:Pro Easter Egg Hunt') and not bsInternal._getPurchased('games.easter_egg_hunt'))):
                unlocked = False

            # lets tint levels a slightly different color when easy mode is selected..
            unlockedColor = (0.85,0.95,0.5) if game.startswith('Easy:') else (0.5,0.7,0.2)

            bs.buttonWidget(edit=self._button,color=unlockedColor if unlocked else (0.5,0.5,0.5))

            bs.imageWidget(edit=self._lockWidget, opacity=0.0 if unlocked else 1.0)
            bs.imageWidget(edit=self._previewWidget, opacity=1.0 if unlocked else 0.3)
            bs.textWidget(edit=self._nameWidget, color=(0.8,1.0,0.8,1.0) if unlocked else (0.7,0.7,0.7,0.7))
            for w in self._starWidgets:
                bs.imageWidget(edit=w, opacity=1.0 if unlocked else 0.3, color=(2.2,1.2,0.3) if unlocked else (1,1,1))
            for i,a in enumerate(self._achievements):
                aComplete = a.isComplete()
                bs.imageWidget(edit=self._achievementWidgets[i][0],opacity=1.0 if (aComplete and unlocked) else 0.3)
                bs.imageWidget(edit=self._achievementWidgets[i][1],opacity=1.0 if (aComplete and unlocked) else 0.2 if aComplete else 0.0)

    class _ChallengeButton(object):

            
        def __init__(self, window, parent, index, x, y, select, row):

            # game = "Challenges:Ninja Fight"
            # self._game = game
            sx = 310.0
            sy = 215.0

            self._waitStart = self._waitEnd = time.time()
            self._start = self._end = time.time()

            # campaignName,levelName = game.split(':')

            # hack - The Last Stand doesn't actually exist in the easy tourney..
            # we just want it for display purposes.. map it to the hard-mode version.
            # if game == 'Easy:The Last Stand':
            #     campaignName = 'Default'

            #campaign = bsCoopGame.getCampaign(campaignName)

            # set to a level name or None if waiting for the next level
            self._gameType = None
            self._waitType = 'nextChallenge'
            self._gameNameTranslated = ""

            self._index = index # temp..
            
            self._window = weakref.ref(window)
            
            self._button = b = bs.buttonWidget(parent=parent,position=(x+23,y+4),size=(sx,sy),label='',
                                               buttonType='square',autoSelect=True,
                                               onActivateCall=bs.WeakCall(self.onPress),
                                               onSelectCall=bs.Call(window._selChange,row,index))
            
            bs.widget(edit=b,showBufferBottom=50,showBufferTop=50,showBufferLeft=400,showBufferRight=200)
            if select:
                bs.containerWidget(edit=parent,selectedChild=b,visibleChild=b)
            imageWidth = sx*0.9*0.75
            self._previewImage = bs.imageWidget(parent=parent,drawController=b,position=(x+21+sx*0.5-imageWidth*0.5,y+sy-169),
                                                 size=(imageWidth,imageWidth*0.5),
                                                 modelTransparent=window._lsbt,modelOpaque=window._lsbo,
                                                 #texture=campaign.getLevel(levelName).getPreviewTex(),
                                                 texture=bs.getTexture('black'),
                                                 maskTexture=bs.getTexture('mapPreviewMask'))

            # self._achievements = bsAchievement.getAchievementsForCoopLevel(game)

            self._nameWidget = bs.textWidget(parent=parent,drawController=b,
                                             position=(x+20+sx*0.5,y+sy-29),
                                             size=(0,0),hAlign='center',
                                             vAlign='center',
                                             maxWidth=sx*0.76,
                                             scale=0.85)
            
            self._levelTextPos = (x+20+sx*0.5,y+sy-53)
            self._levelTextMaxWidth = sx*0.76
            self._levelTextScale = 0.7
            self._levelText = bs.textWidget(parent=parent,drawController=b,
                                            position=self._levelTextPos,
                                            size=(0,0),hAlign='center',
                                            color=(0.9,0.9,0.2),
                                            flatness=1.0,
                                            vAlign='center',
                                            maxWidth=self._levelTextMaxWidth,
                                            scale=self._levelTextScale)
            self._levelChangeText = bs.textWidget(parent=parent,drawController=b,
                                                  size=(0,0),hAlign='left',
                                                  color=(0,1,0),
                                                  flatness=1.0,
                                                  vAlign='center',
                                                  scale=0.55)
            self._totalTimeRemainingText = bs.textWidget(parent=parent,drawController=b,
                                                         position=(x+20+sx*0.5,y+36),
                                                         color=(0.5,0.85,0.5),
                                                         flatness=1.0,
                                                         size=(0,0),
                                                         hAlign='center',
                                                         text='10h 4m 10s',
                                                         vAlign='center',
                                                         maxWidth=sx*0.76,
                                                         scale=0.6)

            rad = 65.0
            self._meterBottom = bs.imageWidget(parent=parent,drawController=b,
                                               position=(x+20+sx*0.5-rad,y+106-rad),
                                               texture=bs.getTexture('circle'),
                                               color=(0,0,0),opacity=0.5,
                                               size=(2.0*rad,2.0*rad))
            rad = 68.0
            self._meterTop = bs.imageWidget(parent=parent,drawController=b,
                                            position=(x+20+sx*0.5-rad,y+106-rad),
                                            texture=bs.getTexture('nub'),
                                            color=(0.47,0.33,0.6),opacity=0.0,
                                            radialAmount=random.random(),
                                            size=(2.0*rad,2.0*rad))

            self._nextText = bs.textWidget(parent=parent,drawController=b,
                                           position=(x+20+sx*0.5,y+sy-104+6),
                                           size=(0,0),hAlign='center',
                                           vAlign='center',
                                           maxWidth=sx*0.76,
                                           color=(0,1,0),
                                           flatness=1.0,
                                           shadow=1.0,
                                           scale=0.67)
            
            
            self._timeRemainingText = bs.textWidget(parent=parent,drawController=b,
                                                    position=(x+20+sx*0.5,y+sy-126+6),
                                                    size=(0,0),hAlign='center',
                                                    vAlign='center',
                                                    maxWidth=sx*0.76,
                                                    color=(0.8,0.7,1),
                                                    flatness=1.0,
                                                    shadow=1.0,
                                                    scale=0.75)
            
            # give a quasi-random update increment to spread the load..
            # (but always making sure we update at least once per second for our timer)
            self._updateTimer = bs.Timer(950+random.randrange(50), bs.WeakCall(self._update),repeat=True,timeType='real')
            self._update()

        def getButton(self):
            return self._button

        def updateForData(self,data):

            if data is None:
                self._gameType = None
                self._waitType = 'nextChallenge'
                self._challengeID = None
                bs.textWidget(edit=self._levelText, text='')
                bs.textWidget(edit=self._levelChangeText, text='')
                bs.textWidget(edit=self._nextText, text='')
                bs.textWidget(edit=self._timeRemainingText, text='')
                bs.imageWidget(edit=self._meterTop,opacity=0.0)
                bs.imageWidget(edit=self._previewImage,texture=bs.getTexture('black'))
                self._waitStart = self._waitEnd = time.time()
                self._start = self._end = time.time()
                self._levelChange = 0
                return

            self._gameType = data['type']
            self._challengeID = data['challengeID']
            
            self._waitStart = data['waitStart']
            self._waitEnd = data['waitEnd']
            self._waitType = data['waitType']
            self._start = data['start']
            self._end = data['end']
            self._levelChange = data['levelChange']
            
            nameTranslated = data['type']
            bs.textWidget(edit=self._nameWidget, text=nameTranslated)
            levelStr = bs.getResource('levelText').replace('${NUMBER}',str(data['level']))
            bs.textWidget(edit=self._levelText, text=levelStr)
            sWidth = min(self._levelTextMaxWidth,(bs.getStringWidth(levelStr)*self._levelTextScale))
            lc = self._levelChange
            changeText = bs.getSpecialChar('upArrow')+str(lc) if lc > 0 else bs.getSpecialChar('downArrow')+str(abs(lc)) if lc < 0 else ''
            bs.textWidget(edit=self._levelChangeText,
                          position=(self._levelTextPos[0]+sWidth*0.5+8,
                                    self._levelTextPos[1]+4),
                          text=changeText)
            bs.textWidget(edit=self._nextText, text='')
            if self._waitType == 'nextPlay':
                bs.textWidget(edit=self._nextText, text=bs.getResource('coopSelectWindow.nextPlayText'))
            else:
                bs.textWidget(edit=self._nextText, text=bs.getResource('coopSelectWindow.nextChallengeText'))
                
            #     bs.imageWidget(edit=self._previewImage,texture=bs.getTexture('black'))
            #     bs.textWidget(edit=self._levelText, text='')
            #     bs.textWidget(edit=self._levelChangeText,text='')
                
            bs.imageWidget(edit=self._previewImage,texture=bs.getTexture('bridgitPreview'))
                
            # this will update opacities/etc..
            self._update()
            
        def onPress(self):
            if self._hasValidData():
                import bsUI2
                bsUI2.ChallengeEntryWindow(challengeID=self._challengeID,
                                           position=self._button.getScreenSpaceCenter())
            else:
                bs.screenMessage(bs.getResource('tournamentCheckingStateText'),color=(1,1,0))
                bs.playSound(bs.getSound('error'))
                

        def _hasValidData(self):
            """ return True if our data is considered up-to-date (so we can launch games, etc) """
            w = self._window()
            if w is None: return False
            else: return w._tourneyDataUpToDate
        
        def _update(self):

            t = time.time()
            
            if self._waitStart == self._waitEnd:
                tRatio = 0.0
                tStr = bsUtils.getTimeString(0)
            else:
                tRatio = (t-self._waitStart)/(self._waitEnd-self._waitStart)
                tRatio = max(0.0, min(1.0, tRatio))
                tStr = bsUtils.getTimeString(max(0,int(self._waitEnd-t))*1000,centi=False)
            if self._start == self._end:
                totalTimeStr = bsUtils.getTimeString(0)
            else:
                totalTimeStr = bsUtils.getTimeString(max(0,int(self._end-t))*1000,centi=False)

            hasValidData = self._hasValidData()
            if self._gameType is not None:
                #unlocked = False if self._index == 1 else True
                outOfTime = True if t > self._end else False
                unlocked = True if t > self._waitEnd and not outOfTime else False
                bs.buttonWidget(edit=self._button,color=(0.5,0.7,0.2) if unlocked else (0.5,0.5,0.5))
                bs.imageWidget(edit=self._previewImage, opacity=1.0 if unlocked else 0.3 if self._waitType == 'nextPlay' else 0.0)
                bs.textWidget(edit=self._nameWidget, color=(0.8,1.0,0.8,1.0) if unlocked else (0.7,0.7,0.7,0.6) if self._waitType == 'nextPlay' else (0,0,0,0))
                lcColor = (0,1,0) if self._levelChange > 0 else (1,0.2,0.3)
                bs.textWidget(edit=self._levelChangeText, color=lcColor if unlocked else (0,0,0,0))
                if not unlocked:
                    # waiting for next challenge..
                    if self._waitType == 'nextChallenge':
                        levelTextColor = (0,0,0,0)
                        totalTimeRemainingColor = (0,0,0,0)
                    # waiting for next play..
                    else:
                        levelTextColor = (0.6,0.6,0.6,0.6)
                        totalTimeRemainingColor = (0.6,0.6,0.6,0.6)
                # available
                else:
                    levelTextColor = (0.9,0.9,0.2)
                    totalTimeRemainingColor = (0.5,0.85,0.5)
                        
                bs.textWidget(edit=self._levelText,color=levelTextColor)
                bs.textWidget(edit=self._totalTimeRemainingText,
                              color=totalTimeRemainingColor,
                              text='' if (self._waitType == 'nextChallenge' and not unlocked) else totalTimeStr if hasValidData else '-')

                bs.imageWidget(edit=self._meterTop,opacity=0.0 if unlocked else 0.0 if outOfTime else 1.0,radialAmount=tRatio)
                bs.imageWidget(edit=self._meterBottom,opacity=0.0 if unlocked else 0.0 if outOfTime else 0.6)
                bs.textWidget(edit=self._timeRemainingText, text='' if (unlocked or outOfTime) else tStr if hasValidData else '-')
                bs.textWidget(edit=self._nextText, color=(0,0,0,0) if (unlocked or outOfTime) else (0.8,0.7,1))
            else:
                # we've got no data..
                bs.buttonWidget(edit=self._button,color=(0.5,0.5,0.5))
                bs.imageWidget(edit=self._previewImage, opacity=0.0)
                bs.textWidget(edit=self._nameWidget, color=(0,0,0,0))
                bs.textWidget(edit=self._totalTimeRemainingText,color=(0,0,0,0))
                bs.imageWidget(edit=self._meterBottom,opacity=0.6 if hasValidData else 0.2)

                bs.imageWidget(edit=self._meterTop,opacity=1.0,radialAmount=tRatio)
                bs.textWidget(edit=self._timeRemainingText, text=tStr if hasValidData else '')
                bs.textWidget(edit=self._nextText, color=(0.8,0.7,1))
                
            
    def _tournamentButton(self,parent,x,y,select):
        sx = 300
        sy = 195.0

        name = ''

        data = {'tournamentID':None,
                'timeRemaining':0,
                'hasTimeRemaining':False,
                'leader':None}
        
        data['button'] = b = bs.buttonWidget(parent=parent,position=(x+23,y+4),size=(sx,sy),label='',
                                                                      buttonType='square',autoSelect=True,
                                                                      #onSelectCall=bs.Call(self._selChange,row,None),
                                                                      onActivateCall=bs.Call(self._run,None,tournamentButton=data))
        bs.widget(edit=b,showBufferBottom=50,showBufferTop=50,showBufferLeft=400,showBufferRight=200)
        if select: bs.containerWidget(edit=parent,selectedChild=b,visibleChild=b)
        imageWidth = sx*0.85*0.75
        
        data['image'] = bs.imageWidget(parent=parent,drawController=b,position=(x+21+sx*0.5-imageWidth*0.5,y+sy-150),
                                       size=(imageWidth,imageWidth*0.5),modelTransparent=self._lsbt,modelOpaque=self._lsbo,
                                       texture=bs.getTexture('black'),opacity=0.2,maskTexture=bs.getTexture('mapPreviewMask'))

        data['lockImage'] = bs.imageWidget(parent=parent,drawController=b,position=(x+21+sx*0.5-imageWidth*0.25,y+sy-150),
                                           size=(imageWidth*0.5,imageWidth*0.5),
                                           texture=bs.getTexture('lock'),opacity=0.0)
        
        data['buttonText'] = bs.textWidget(parent=parent,drawController=b,position=(x+20+sx*0.5,y+sy-35),
                                           size=(0,0),hAlign='center',text='-',vAlign='center',maxWidth=sx*0.76,
                                           scale=0.85,color=(0.8,1.0,0.8,1.0))

        headerColor = (0.43,0.4,0.5,1)
        valueColor = (0.6,0.6,0.6,1)

        xOffs = 0
        bs.textWidget(parent=parent,drawController=b,position=(x+360,y+sy-20),
                      size=(0,0),hAlign='center',text=self._R.entryFeeText,vAlign='center',maxWidth=100,
                      scale=0.9,color=headerColor,flatness=1.0)

        data['entryFeeTextTop'] = bs.textWidget(parent=parent,drawController=b,position=(x+360,y+sy-60),
                                              size=(0,0),hAlign='center',text='-',
                                              vAlign='center',maxWidth=60,scale=1.3,color=valueColor,flatness=1.0)
        data['entryFeeTextOr'] = bs.textWidget(parent=parent,drawController=b,position=(x+360,y+sy-90),
                                              size=(0,0),hAlign='center',text='',
                                              vAlign='center',maxWidth=60,scale=0.5,color=valueColor,flatness=1.0)
        data['entryFeeTextRemaining'] = bs.textWidget(parent=parent,drawController=b,position=(x+360,y+sy-90),
                                                      size=(0,0),hAlign='center',text='',
                                                      vAlign='center',maxWidth=60,scale=0.5,color=valueColor,flatness=1.0)

        data['entryFeeAdImage'] = bs.imageWidget(parent=parent,size=(40,40),
                                               drawController=b,
                                               position=(x+360-20,y+sy-140),opacity=0.0,
                                               texture=bs.getTexture('tv'))

        
        xOffs += 50

        
        bs.textWidget(parent=parent,drawController=b,position=(x+447+xOffs,y+sy-20),
                      size=(0,0),hAlign='center',text=self._R.prizesText,vAlign='center',maxWidth=130,
                      scale=0.9,color=headerColor,flatness=1.0)

        data['buttonX'] = x
        data['buttonY'] = y
        data['buttonScaleY'] = sy

        xo2 = 0

        prizeValueScale = 1.5
        
        data['prizeRange1Text'] = bs.textWidget(parent=parent,drawController=b,position=(x+355+xo2+xOffs,y+sy-93),
                                                size=(0,0),hAlign='right',vAlign='center',maxWidth=50,text='-',
                                                scale=0.8,color=headerColor,flatness=1.0)
        data['prizeValue1Text'] = bs.textWidget(parent=parent,drawController=b,position=(x+380+xo2+xOffs,y+sy-93),
                                                size=(0,0),hAlign='left',text='-',vAlign='center',maxWidth=100,
                                                scale=prizeValueScale,color=valueColor,flatness=1.0)

        data['prizeRange2Text'] = bs.textWidget(parent=parent,drawController=b,position=(x+355+xo2+xOffs,y+sy-93),
                                                size=(0,0),hAlign='right',vAlign='center',maxWidth=50,
                                                scale=0.8,color=headerColor,flatness=1.0)
        data['prizeValue2Text'] = bs.textWidget(parent=parent,drawController=b,position=(x+380+xo2+xOffs,y+sy-93),
                                                size=(0,0),hAlign='left',text='',vAlign='center',maxWidth=100,
                                                scale=prizeValueScale,color=valueColor,flatness=1.0)

        data['prizeRange3Text'] = bs.textWidget(parent=parent,drawController=b,position=(x+355+xo2+xOffs,y+sy-93),
                                                size=(0,0),hAlign='right',vAlign='center',maxWidth=50,
                                                scale=0.8,color=headerColor,flatness=1.0)
        data['prizeValue3Text'] = bs.textWidget(parent=parent,drawController=b,position=(x+380+xo2+xOffs,y+sy-93),
                                                size=(0,0),hAlign='left',text='',vAlign='center',maxWidth=100,
                                                scale=prizeValueScale,color=valueColor,flatness=1.0)
        
        bs.textWidget(parent=parent,drawController=b,position=(x+620+xOffs,y+sy-20),
                      size=(0,0),hAlign='center',text=self._R.currentBestText,vAlign='center',maxWidth=180,
                      scale=0.9,color=headerColor,flatness=1.0)
        # data['currentLeaderNameButton'] = bs.buttonWidget(parent=parent,position=(x+620+xOffs,y+sy-60),
        #                                                   size=(200,30),label='-',scale=1.4,textColor=valueColor)
        data['currentLeaderNameText'] = bs.textWidget(parent=parent,drawController=b,position=(x+620+xOffs-(170/1.4)*0.5,y+sy-60-40*0.5),
                                                      selectable=True,clickActivate=True,autoSelect=True,
                                                      onActivateCall=lambda: self._showLeader(tournamentButton=data),
                                                      size=(170/1.4,40),hAlign='center',text='-',
                                                      vAlign='center',maxWidth=170,scale=1.4,color=valueColor,flatness=1.0)
        # data['currentLeaderNameText'] = bs.textWidget(parent=parent,drawController=b,position=(x+620+xOffs,y+sy-60),
        #                                               selectable=True,clickActivate=True,autoSelect=True,
        #                                               onActivateCall=foo,size=(0,0),hAlign='center',text='-',
        #                                               vAlign='center',maxWidth=170,scale=1.4,color=valueColor,flatness=1.0)
        data['currentLeaderScoreText'] = bs.textWidget(parent=parent,drawController=b,position=(x+620+xOffs,y+sy-113+10),
                                                       size=(0,0),hAlign='center',text='-',
                                                       vAlign='center',maxWidth=170,scale=1.8,color=valueColor,flatness=1.0)

        data['moreScoresButton'] = bs.buttonWidget(parent=parent,position=(x+620+xOffs-60,y+sy-50-125),
                                                   color=(0.5,0.5,0.6),textColor=(0.7,0.7,0.8),
                                                   label='-',size=(120,40),autoSelect=True,
                                                   upWidget=data['currentLeaderNameText'],
                                                   textScale=0.6,
                                                   onActivateCall=lambda: self._showScores(tournamentButton=data))
        bs.widget(edit=data['currentLeaderNameText'],downWidget=data['moreScoresButton'])
        
        bs.textWidget(parent=parent,drawController=b,position=(x+820+xOffs,y+sy-20),
                      size=(0,0),hAlign='center',text=self._R.timeRemainingText,vAlign='center',maxWidth=180,
                      scale=0.9,color=headerColor,flatness=1.0)
        data['timeRemainingValueText'] = bs.textWidget(parent=parent,drawController=b,position=(x+820+xOffs,y+sy-68),
                                                               size=(0,0),hAlign='center',text='-',
                                                               vAlign='center',maxWidth=180,scale=2.0,color=valueColor,flatness=1.0)
        data['timeRemainingOutOfText'] = bs.textWidget(parent=parent,drawController=b,position=(x+820+xOffs,y+sy-110),
                                                       size=(0,0),hAlign='center',text='-',
                                                       vAlign='center',maxWidth=120,scale=0.72,color=(0.4,0.4,0.5),flatness=1.0)
        return data

    def _switchToPowerRankings(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = PowerRankingWindow(originWidget=self._powerRankingButtonInstance.getButtonWidget()).getRootWidget()
    
    def _switchToStore(self,showTab='extras'):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = StoreWindow(originWidget=self._storeButtonInstance.getButtonWidget(),showTab=showTab,backLocation='CoopWindow').getRootWidget()
        

    def _showLeader(self,tournamentButton):
        tournamentID = tournamentButton['tournamentID']
        # FIXME - this assumes a single player entry in leader; should expand this to work with multiple
        if tournamentID is None or tournamentButton['leader'] is None or len(tournamentButton['leader'][2]) != 1:
            bs.playSound(bs.getSound('error'))
            return
        bs.playSound(bs.getSound('swish'))
        AccountInfoWindow(accountID=tournamentButton['leader'][2][0].get('a',None),
                          profileID=tournamentButton['leader'][2][0].get('p',None),
                          position=tournamentButton['currentLeaderNameText'].getScreenSpaceCenter())
        
    def _showScores(self,tournamentButton):
        tournamentID = tournamentButton['tournamentID']
        if tournamentID is None:
            bs.playSound(bs.getSound('error'))
            return

        TournamentScoresWindow(tournamentID=tournamentID,
                               position=tournamentButton['moreScoresButton'].getScreenSpaceCenter())
        
    def _run(self,game,tournamentButton=None):

        args = {}
        
        # do a bit of pre-flight for tournament options:
        if tournamentButton is not None:

            if bsInternal._getAccountState() != 'SIGNED_IN':
                showSignInPrompt()
                return

            if not self._tourneyDataUpToDate:
                bs.screenMessage(bs.getResource('tournamentCheckingStateText'),color=(1,1,0))
                bs.playSound(bs.getSound('error'))
                return
                
            if tournamentButton['tournamentID'] is None:
                bs.screenMessage(bs.getResource('internal.unavailableNoConnectionText'),color=(1,0,0))
                bs.playSound(bs.getSound('error'))
                return

            if tournamentButton['requiredLeague'] is not None:
                bs.screenMessage(bs.getResource('league.tournamentLeagueText').replace('${NAME}',bs.translate('leagueNames',tournamentButton['requiredLeague'])),color=(1,0,0))
                bs.playSound(bs.getSound('error'))
                return
                
            if tournamentButton['timeRemaining'] <= 0:
                bs.screenMessage(bs.getResource('tournamentEndedText'),color=(1,0,0))
                bs.playSound(bs.getSound('error'))
                return

            # game is whatever the tournament tells us it is
            game = gTournamentInfo[tournamentButton['tournamentID']]['game']
            
        if tournamentButton is None and game == 'Easy:The Last Stand':
            ConfirmWindow(bs.getResource('difficultyHardUnlockOnlyText',fallback='difficultyHardOnlyText'),cancelButton=False,width=460,height=130)
            return
        
        # infinite onslaught/runaround require pro; bring up a store link if need be.
        if tournamentButton is None and game in ('Challenges:Infinite Runaround','Challenges:Infinite Onslaught') and not bsUtils._havePro():
            if bsInternal._getAccountState() != 'SIGNED_IN':
                showSignInPrompt()
            else:
                PurchaseWindow(items=['pro'])
            return

        if game in ['Challenges:Meteor Shower']: requiredPurchase = 'games.meteor_shower'
        elif game in ['Challenges:Target Practice','Challenges:Target Practice B']: requiredPurchase = 'games.target_practice'
        elif game in ['Challenges:Ninja Fight']:  requiredPurchase = 'games.ninja_fight'
        elif game in ['Challenges:Pro Ninja Fight']: requiredPurchase = 'games.ninja_fight'
        elif game in ['Challenges:Easter Egg Hunt','Challenges:Pro Easter Egg Hunt']: requiredPurchase = 'games.easter_egg_hunt'
        else: requiredPurchase = None
        
        if tournamentButton is None and requiredPurchase is not None and not bsInternal._getPurchased(requiredPurchase):
            if bsInternal._getAccountState() != 'SIGNED_IN':
                showSignInPrompt()
            else:
                PurchaseWindow(items=[requiredPurchase])
            return
        
        self._saveState()
        
        # for tournaments, we pop up the entry window
        if tournamentButton is not None:
            TournamentEntryWindow(tournamentID=tournamentButton['tournamentID'],
                                  position=tournamentButton['button'].getScreenSpaceCenter())
        else:
            # otherwise just dive right in..
            if bsUtils._handleRunChallengeGame(game,args=args):
                bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _back(self):
        # if something is selected, store it

        self._saveState()
        
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = PlayWindow(transition='inLeft').getRootWidget()

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]['selName']
            except Exception: selName = None
            if selName == 'Back': sel = self._backButton
            elif selName == 'Scroll': sel = self._scrollWidget
            elif selName == 'PowerRanking': sel = self._powerRankingButton
            elif selName == 'Store': sel = self._storeButton
            else: sel = self._scrollWidget
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)
        
    def _saveState(self):
        cfg = bs.getConfig()

        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._backButton: selName = 'Back'
            elif sel == self._storeButton: selName = 'Store'
            elif sel == self._powerRankingButton: selName = 'PowerRanking'
            elif sel == self._scrollWidget: selName = 'Scroll'
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = {'selName':selName}
        except Exception:
            bs.printException('error saving state for',self.__class__)
        
        cfg['Selected Coop Row'] = self._selectedRow
        cfg['Selected Coop Custom Level'] = self._selectedCustomLevel
        cfg['Selected Coop Challenge Level'] = self._selectedChallengeLevel
        cfg['Selected Coop Campaign Level'] = self._selectedCampaignLevel
        bs.writeConfig()
            
    def _selChange(self,row,game):
        if self._doSelectionCallbacks:
            if row == 'custom': self._selectedCustomLevel = game
            if row == 'challenges': self._selectedChallengeLevel = game
            elif row == 'campaign': self._selectedCampaignLevel = game

def pause():

    # if there's a foreground host-activity that says it's pausable, tell it to pause
    activity = bsInternal._getForegroundHostActivity()
    if activity is not None and activity._allowPausing:
        with bs.Context(activity):
            g = bs.getSharedObject('globals')
            if not g.paused:
                bs.playSound(bs.getSound('refWhistle'))
                g.paused = True
            activity._pausedText = bs.NodeActor(bs.newNode('text',
                                                          attrs={'text':bs.getResource('pausedByHostText'),
                                                                 'clientOnly':True,
                                                                 'flatness':1.0,
                                                                 'hAlign':'center'}))

def resume():

    # if there's a foreground host-activity that's currently paused, tell it to resume
    activity = bsInternal._getForegroundHostActivity()
    if activity is not None:
        with bs.Context(activity):
            g = bs.getSharedObject('globals')
            if g.paused:
                bs.playSound(bs.getSound('refWhistle'))
                g.paused = False
                activity._pausedText = None

gMainMenuResumeCallbacks = []

def addMainMenuCloseCallback(call):

    # if there's no main menu up, just call immediately
    if uiGlobals['mainMenuWindow'] is None or not uiGlobals['mainMenuWindow'].exists():
        with bs.Context('UI'): call()
    else:
        gMainMenuResumeCallbacks.append(call)


gMainMenuWindowRefreshCheckCount = 0

gFirstMainMenu = True

class MainMenuWindow(Window):

    def __init__(self,transition='inRight'):

        import bsMainMenu
        global gFirstMainMenu

        self._inGame = not isinstance(bsInternal._getForegroundHostSession(),bsMainMenu.MainMenuSession)
        if not self._inGame:
            bsInternal._setAnalyticsScreen('Main Menu')
            
            # the first time the non-in-game menu pops up, we might wanna show a 'get-remote-app' dialog in front of it
            if gFirstMainMenu:
                gFirstMainMenu = False
                try:
                    env = bs.getEnvironment()
                    forceTest = False
                    dCount = bsInternal._getLocalActiveInputDevicesCount()
                    # if (env['onTV'] and (env['platform'] == 'android' and env['subplatform'] == 'alibaba') and dCount < 1) or forceTest:
                    if ((env['onTV'] or env['platform'] == 'mac') and bs.getConfig().get('launchCount',0) <= 1) or forceTest:
                    #if ((env['onTV'] or env['platform'] == 'mac') and bs.getConfig().get('launchCount',0) > 1) or forceTest:
                    # print 'LC',bs.getConfig().get('launchCount',0)
                    # if True and bs.getConfig().get('launchCount',0) < 3:
                        def _checkShowBSRemoteWindow():
                            try:
                                import bsUI2
                                bs.playSound(bs.getSound('swish'))
                                bsUI2.GetBSRemoteWindow()
                            except Exception:
                                bs.printException('error showing bs-remote window')
                        bs.realTimer(2500,_checkShowBSRemoteWindow)
                except Exception as e:
                    print 'EXC bsRemoteShow',e
                            

        # make a vanilla container; we'll modify it to our needs in refresh
        self._rootWidget = bs.containerWidget(transition=transition)

        self._storeCharTex = self._getStoreCharTex()
        
        self._refresh()
        self._restoreState()

        # keep an eye on a few things and refresh if they change
        self._accountState = bsInternal._getAccountState()
        self._accountStateNum = bsInternal._getAccountStateNum()
        self._accountType = bsInternal._getAccountType() if self._accountState == 'SIGNED_IN' else None
        self._refreshTimer = bs.Timer(1000,bs.WeakCall(self._checkRefresh),repeat=True,timeType='real')

    def _getStoreCharTex(self):
        return 'storeCharacterXmas' if bsInternal._getAccountMiscReadVal('xmas',False) else 'storeCharacterEaster' if bsInternal._getAccountMiscReadVal('easter',False) else 'storeCharacter'
    
    def _checkRefresh(self):

        if not self._rootWidget.exists(): return
        
        # dont refresh for the first few seconds the game is up so we don't interrupt the transition in
        global gMainMenuWindowRefreshCheckCount
        gMainMenuWindowRefreshCheckCount += 1
        if gMainMenuWindowRefreshCheckCount < 3: return

        storeCharTex = self._getStoreCharTex()
        
        accountStateNum = bsInternal._getAccountStateNum()
        if accountStateNum != self._accountStateNum or storeCharTex != self._storeCharTex:
            self._storeCharTex = storeCharTex
            self._accountStateNum = accountStateNum
            accountState = self._accountState = bsInternal._getAccountState()
            self._accountType = bsInternal._getAccountType() if accountState == 'SIGNED_IN' else None
            self._saveState()
            self._refresh()
            self._restoreState()

    def getPlayButton(self):
        return self._startButton
    
    def _refresh(self):

        # clear everything that was there..
        children = self._rootWidget.getChildren()
        for c in children: c.delete()
        
        # alter some default behavior when going through the main menu..
        if not self._inGame:
            bsUtils.gRunningKioskModeGame = False
        
        #useAutoSelect = False if self._inGame else True
        useAutoSelect = True
        
        buttonHeight = 45
        buttonWidth = 200
        padding = 10

        tDelay = 0
        tDelayInc = 0
        tDelayPlay = 0

        self._R = R = bs.getResource('mainMenu')

        env = bs.getEnvironment()
        self._haveQuitButton = env['interfaceType'] == 'desktop' or bsInternal._isOuyaBuild() or (env['platform'] == 'windows' and env['subplatform'] == 'oculus')

        self._haveStoreButton = True if not self._inGame else False

        self._inputDevice = inputDevice = bsInternal._getUIInputDevice()
        self._inputPlayer = inputDevice.getPlayer() if inputDevice is not None else None
        if self._inputPlayer is not None and not self._inputPlayer.exists(): self._inputPlayer = None
        self._connectedToRemotePlayer = inputDevice.isConnectedToRemotePlayer() if inputDevice is not None else False

        
        positions = []
        pIndex = 0
        
        if self._inGame:

            customMenuEntries = []
            session = bsInternal._getForegroundHostSession()
            if session is not None:
                try:
                    customMenuEntries = session.getCustomMenuEntries()
                    for c in customMenuEntries:
                        if (type(c) is not dict or not 'label' in c or type(c['label']) not in (str,unicode)
                            or 'call' not in c or not callable(c['call'])):
                            raise Exception("invalid custom menu entry: "+str(c))
                except Exception:
                    customMenuEntries = []
                    bs.printException('exception getting custom menu entries for',session)

            self._width = 250
            self._height = 250 if self._inputPlayer is not None else 180
            if self._connectedToRemotePlayer: self._height += 50 # in this case we have a leave *and* a disconnect button
            self._height += 50*(len(customMenuEntries))
            bs.containerWidget(edit=self._rootWidget,size=(self._width,self._height),scale=2.15 if gSmallUI else 1.6 if gMedUI else 1.0)
            h = 125
            v = self._height-80 if self._inputPlayer is not None else self._height-60
            hOffset = 0
            dhOffset = 0
            vOffset = -50
            for i in range(6+len(customMenuEntries)):
                positions.append((h,v,1.0))
                v += vOffset; h += hOffset; hOffset += dhOffset

        # not in game
        else:
            global gDidMenuIntro
            if gDidMenuIntro == False:
                tDelay = 2000
                tDelayInc = 20
                tDelayPlay = 1700
                gDidMenuIntro = True

            self._width = 400
            self._height = 200

            accountType = bsInternal._getAccountType() if bsInternal._getAccountState() == 'SIGNED_IN' else None
            enableAccountButton = True

            # if bsInternal._getAccountState() == 'SIGNED_IN' and accountType != 'Local':
            if bsInternal._getAccountState() == 'SIGNED_IN':
                accountTypeName = bsInternal._getAccountDisplayString()
                accountTypeIcon = None
                accountTextColor = (1,1,1)
            else:
                accountTypeName = bs.getResource('notSignedInText',fallback='accountSettingsWindow.titleText')
                accountTypeIcon = None
                accountTextColor = (1,0.2,0.2)
            accountTypeIconColor = (1,1,1)
            accountTypeCall = self._showAccountWindow
            accountTypeEnableButtonSound = True

            bCount = 4 # play, help, credits, settings
            if enableAccountButton: bCount += 1
            if self._haveQuitButton: bCount += 1
            if self._haveStoreButton: bCount += 1

            if gSmallUI:
                rootWidgetScale = 1.6
                playButtonWidth = buttonWidth*0.65
                playButtonHeight = buttonHeight*1.1
                smallButtonScale = 0.51 if bCount > 6 else 0.63
                buttonYOffs = -20
                buttonYOffs2 = -60
                buttonHeight *= 1.3
                buttonSpacing = 1.04
            elif gMedUI:
                rootWidgetScale = 1.3
                playButtonWidth = buttonWidth*0.65
                playButtonHeight = buttonHeight*1.1
                smallButtonScale = 0.6
                buttonYOffs = -55
                buttonYOffs2 = -75
                buttonHeight *= 1.25
                buttonSpacing = 1.1
            else:
                rootWidgetScale = 1.0
                playButtonWidth = buttonWidth*0.65
                playButtonHeight = buttonHeight*1.1
                smallButtonScale = 0.75
                buttonYOffs = -80
                buttonYOffs2 = -100
                buttonHeight *= 1.2
                buttonSpacing = 1.1

            spc = buttonWidth*smallButtonScale*buttonSpacing

            bs.containerWidget(edit=self._rootWidget,size=(self._width,self._height),background=False,scale=rootWidgetScale)

            positions = [[self._width*0.5,buttonYOffs,1.7]]
            xOffs = self._width*0.5-(spc*(bCount-1)*0.5)+(spc*0.5)
            for i in range(bCount-1):
                positions.append([xOffs+spc*i-1.0,buttonYOffs+buttonYOffs2,smallButtonScale])

        if not self._inGame:

            # in kiosk mode, provide a button to get back to the kiosk menu
            if bs.getEnvironment()['kioskMode']:
                h,v,scale = positions[pIndex]
                thisBWidth = buttonWidth*0.4*scale
                demoMenuDelay = 0 if tDelayPlay == 0 else max(0,tDelayPlay+100)
                self._demoMenuButton = bs.buttonWidget(parent=self._rootWidget,
                                                       position=(self._width*0.5-thisBWidth*0.5,v+90),size=(thisBWidth,45),autoSelect=True,
                                                       color=(0.45,0.55,0.45),textColor=(0.7,0.8,0.7),
                                                       label=self._R.demoMenuText,transitionDelay=demoMenuDelay,onActivateCall=self._demoMenuPress)
            else: self._demoMenuButton = None
                            

            
            # if bsInternal._isOuyaBuild():
            #     self._demoVersionUpdateTimer = bs.Timer(1000,bs.WeakCall(self._updateDemoButton),repeat=True,timeType='real')


            foo = -1 if gSmallUI else 1 if gMedUI else 3
            
            h,v,scale = positions[pIndex]
            v = v + foo
            gatherDelay = 0 if tDelayPlay == 0 else max(0,tDelayPlay+100)
            thisH = h-playButtonWidth*0.5*scale-40*scale
            thisBWidth = buttonWidth*0.25*scale
            thisBHeight = buttonHeight*0.82*scale
            self._gatherButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                     position=(thisH-thisBWidth*0.5,v),
                                                     size=(thisBWidth,thisBHeight),autoSelect=useAutoSelect,
                                                     #scale=scale,
                                                     #textScale=0.8,
                                                     buttonType='square',
                                                     #label = bs.getResource('gatherWindow.titleText'),
                                                     label='',
                                                     transitionDelay=gatherDelay,
                                                     onActivateCall=self._gatherPress)
            bs.textWidget(parent=self._rootWidget,
                          position=(thisH,v+buttonHeight*0.33),
                          size=(0,0),
                          scale=0.75,
                          transitionDelay=gatherDelay,
                          drawController=b,
                          color=(0.75,1.0,0.7),
                          maxWidth=buttonWidth*0.33,
                          text=bs.getResource('gatherWindow.titleText'),
                          hAlign='center',vAlign='center')
            iconSize = thisBWidth*0.6
            bs.imageWidget(parent=self._rootWidget,size=(iconSize,iconSize),
                           drawController=b,
                           transitionDelay=gatherDelay,
                           position=(thisH-0.5*iconSize,v+0.31*thisBHeight),
                           texture=bs.getTexture('usersButton'))
            
            # play button
            h,v,scale = positions[pIndex]
            pIndex += 1
            self._startButton = startButton = b = bs.buttonWidget(parent=self._rootWidget, position=(h - playButtonWidth*0.5*scale,v),
                                                                  size=(playButtonWidth,playButtonHeight),autoSelect=useAutoSelect,
                                                                  scale=scale,
                                                                  textResScale=2.0,
                                                                  label = bs.getResource('playText'),
                                                                  transitionDelay=tDelayPlay,
                                                                  onActivateCall=self._playPress)

            bs.containerWidget(edit=self._rootWidget,startButton=startButton,selectedChild=startButton)

            v = v + foo

            watchDelay = 0 if tDelayPlay == 0 else max(0,tDelayPlay-100)
            thisH = h+playButtonWidth*0.5*scale+40*scale
            thisBWidth = buttonWidth*0.25*scale
            thisBHeight = buttonHeight*0.82*scale
            self._watchButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                    position=(thisH-thisBWidth*0.5,v),
                                                    size=(thisBWidth,thisBHeight),autoSelect=useAutoSelect,
                                                    buttonType='square',
                                                    label='',
                                                    transitionDelay=watchDelay,
                                                    onActivateCall=self._watchPress)

            bs.textWidget(parent=self._rootWidget,
                          position=(thisH,v+buttonHeight*0.33),
                          size=(0,0),
                          scale=0.75,
                          transitionDelay=watchDelay,
                          color=(0.75,1.0,0.7),
                          drawController=b,
                          maxWidth=buttonWidth*0.33,
                          text=bs.getResource('watchWindow.titleText'),
                          hAlign='center',vAlign='center')
            iconSize = thisBWidth*0.55
            bs.imageWidget(parent=self._rootWidget,size=(iconSize,iconSize),
                           drawController=b,
                           transitionDelay=watchDelay,
                           position=(thisH-0.5*iconSize,v+0.33*thisBHeight),
                           texture=bs.getTexture('tv'))
            
            if not self._inGame and enableAccountButton:
                thisBWidth = buttonWidth
                h,v,scale = positions[pIndex]
                pIndex += 1
                self._gcButton = gcButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h - thisBWidth*0.5*scale,v),size=(thisBWidth,buttonHeight),scale=scale,
                                                                label=accountTypeName,autoSelect=useAutoSelect,
                                                                onActivateCall=accountTypeCall,
                                                                textColor=accountTextColor,
                                                                icon=accountTypeIcon,
                                                                iconColor=accountTypeIconColor,
                                                                transitionDelay=tDelay,
                                                                enableSound=accountTypeEnableButtonSound)
                                                                #selectable=False if (accountType == 'Game Center' and bs.getEnvironment()['platform'] == 'mac') else True)

                # scattered eggs on easter
                if bsInternal._getAccountMiscReadVal('easter',False) and not self._inGame:
                    iconSize = 32
                    iw = bs.imageWidget(parent=self._rootWidget,position=(h - iconSize*0.5+35,v+buttonHeight*scale-iconSize*0.24+1.5),transitionDelay=tDelay,
                                        size=(iconSize,iconSize),
                                        texture=bs.getTexture('egg2'),tiltScale=0.0)
                                                                
                tDelay += tDelayInc
            else: self._gcButton = None
            
            # how-to-play button
            h,v,scale = positions[pIndex]
            pIndex += 1
            self._howToPlayButton = howToPlayButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h - buttonWidth*0.5*scale,v),
                                                                          scale=scale,autoSelect=useAutoSelect,
                                                                          size=(buttonWidth,buttonHeight),
                                                                          label = R.howToPlayText,
                                                                          transitionDelay=tDelay,
                                                                          onActivateCall=self._howToPlay)

            # scattered eggs on easter
            if bsInternal._getAccountMiscReadVal('easter',False) and not self._inGame:
                iconSize = 28
                iw = bs.imageWidget(parent=self._rootWidget,position=(h - iconSize*0.5+30,v+buttonHeight*scale-iconSize*0.24+1.5),transitionDelay=tDelay,
                                    size=(iconSize,iconSize),
                                    texture=bs.getTexture('egg4'),tiltScale=0.0)
            

            # credits button
            tDelay += tDelayInc
            h,v,scale = positions[pIndex]
            pIndex += 1
            creditsText = R.creditsText
            self._creditsButton = creditsButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h - buttonWidth*0.5*scale,v),
                                                                      size=(buttonWidth,buttonHeight),autoSelect=useAutoSelect,
                                                                      label = creditsText,
                                                                      scale=scale,
                                                                      transitionDelay=tDelay,
                                                                      onActivateCall=self._credits)
            tDelay += tDelayInc

        # in-game
        else:
            self._startButton = None
            
            pause()
            #print 'WARNING: need to fix pausing2'
            #if bs.getSharedObject('globals').allowPausing and transition == 'inRight': bs.playSound(bs.getSound('refWhistle'))
            #if True and transition == 'inRight': bs.playSound(bs.getSound('refWhistle'))

            # (player name if applicable)
            if self._inputPlayer is not None:
                playerName = self._inputPlayer.getName()
                h,v,scale = positions[pIndex]
                v += 35
                b = bs.textWidget(parent=self._rootWidget, position=(h - buttonWidth/2,v), size=(buttonWidth,buttonHeight),
                                  color=(1,1,1,0.5),
                                  scale=0.7,
                                  hAlign='center',
                                  text = playerName)
            else: playerName = ''

            h,v,scale = positions[pIndex]
            pIndex += 1

            b = bs.buttonWidget(parent=self._rootWidget, position=(h - buttonWidth/2,v), size=(buttonWidth,buttonHeight),scale=scale,
                                label = R.resumeText,autoSelect=useAutoSelect,
                                onActivateCall=self._resume)
            bs.containerWidget(edit=self._rootWidget,cancelButton=b)

            # add any custom options defined by the current game
            for entry in customMenuEntries:
                h,v,scale = positions[pIndex]
                pIndex += 1

                # ask the entry whether we should resume when we call it (defaults to true)
                try: resume = entry['resumeOnCall']
                except Exception: resume = True

                if resume: call = bs.Call(self._resumeAndCall,entry['call'])
                else: call = bs.Call(entry['call'],bs.WeakCall(self._resume))
                
                b = bs.buttonWidget(parent=self._rootWidget, position=(h - buttonWidth/2,v), size=(buttonWidth,buttonHeight),scale=scale,
                                    onActivateCall=call,label=entry['label'],autoSelect=useAutoSelect)

            # add a 'leave' button if the menu-owner has a player
            if self._inputPlayer is not None or self._connectedToRemotePlayer:
                h,v,scale = positions[pIndex]
                pIndex += 1
                b = bs.buttonWidget(parent=self._rootWidget, position=(h - buttonWidth/2,v), size=(buttonWidth,buttonHeight),scale=scale,
                                    onActivateCall=self._leave,label='',autoSelect=useAutoSelect)
                                    #onActivateCall=self._leave,label = R.leaveText,autoSelect=useAutoSelect)
                if playerName != u'' and playerName[0] != u'<' and playerName[-1] != u'>': t = bs.uni(self._R.justPlayerText).replace(u'${NAME}',playerName)
                else: t = playerName
                bs.textWidget(parent=self._rootWidget,position=(h,v+buttonHeight*(0.64 if t != '' else 0.5)),size=(0,0),text=R.leaveGameText,scale=(0.83 if t != '' else 1.0),
                              color=(0.75,1.0,0.7),hAlign='center',vAlign='center',drawController=b,maxWidth=buttonWidth*0.9)
                bs.textWidget(parent=self._rootWidget,position=(h,v+buttonHeight*0.27),size=(0,0),text=t,
                              color=(0.75,1.0,0.7),hAlign='center',vAlign='center',drawController=b,scale=0.45,maxWidth=buttonWidth*0.9)
                
            # for ui in customMenuEntries2:
            #     h,v,scale = positions[pIndex]
            #     pIndex += 1
            #     b = bs.buttonWidget(parent=self._rootWidget, position=(h - buttonWidth/2,v), size=(buttonWidth,buttonHeight),scale=scale,
            #                         onActivateCall=bs.Call(self._resumeAndCall,ui[1]),label = ui[0])

        h,v,scale = positions[pIndex]
        pIndex += 1

        self._settingsButton = settingsButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h - buttonWidth*0.5*scale,v),size=(buttonWidth,buttonHeight),scale=scale,
                                                                    autoSelect=useAutoSelect,label=R.settingsText,transitionDelay=tDelay,onActivateCall=self._settings)

        # scattered eggs on easter
        if bsInternal._getAccountMiscReadVal('easter',False) and not self._inGame:
            iconSize = 34
            iw = bs.imageWidget(parent=self._rootWidget,position=(h - iconSize*0.5-15,v+buttonHeight*scale-iconSize*0.24+1.5),transitionDelay=tDelay,
                                size=(iconSize,iconSize),
                                texture=bs.getTexture('egg3'),tiltScale=0.0)
        
        tDelay += tDelayInc

        if self._inGame:
            h,v,scale = positions[pIndex]
            pIndex += 1

            # if we're in a replay, we have a 'Leave Replay' button
            if bsInternal._isInReplay():
                b = bs.buttonWidget(parent=self._rootWidget,position=(h - buttonWidth*0.5*scale,v),scale=scale,
                                    size=(buttonWidth,buttonHeight),autoSelect=useAutoSelect,
                                    label = bs.getResource('replayEndText'),
                                    onActivateCall=self._confirmEndReplay)
            elif bsInternal._getForegroundHostSession() is not None:
                b = bs.buttonWidget(parent=self._rootWidget,position=(h - buttonWidth*0.5*scale,v),scale=scale,
                                    size=(buttonWidth,buttonHeight),autoSelect=useAutoSelect,
                                    label = R.endGameText,
                                    onActivateCall=self._confirmEndGame)
            # assume we're in a client-session..
            else:
                b = bs.buttonWidget(parent=self._rootWidget,position=(h - buttonWidth*0.5*scale,v),scale=scale,
                                    size=(buttonWidth,buttonHeight),autoSelect=useAutoSelect,
                                    label = R.leavePartyText,
                                    onActivateCall=self._confirmLeaveParty)
                


        if self._haveStoreButton:
            thisBWidth = buttonWidth
            h,v,scale = positions[pIndex]
            pIndex += 1

            sb = self._storeButtonInstance = StoreButton(parent=self._rootWidget,position=(h - thisBWidth*0.5*scale,v),
                                                         size=(thisBWidth,buttonHeight),scale=scale,
                                                         onActivateCall=bs.WeakCall(self._onStorePressed),
                                                         saleScale=1.3,
                                                         transitionDelay=tDelay)
            self._storeButton = storeButton = sb.getButtonWidget()
            # self._storeButton = storeButton = b = bs.buttonWidget(parent=self._rootWidget,position=(h - thisBWidth*0.5*scale,v),
            #                                                       size=(thisBWidth,buttonHeight),scale=scale,autoSelect=useAutoSelect,
            #                                                       label=bs.getResource('storeText'),
            #                                                       onActivateCall=self._onStorePressed,
            #                                                       transitionDelay=tDelay)
            iconSize = 55 if gSmallUI else 55 if gMedUI else 70
            iw = bs.imageWidget(parent=self._rootWidget,position=(h - iconSize*0.5,v+buttonHeight*scale-iconSize*0.23),transitionDelay=tDelay,size=(iconSize,iconSize),
                                texture=bs.getTexture(self._storeCharTex),tiltScale=0.0,drawController=storeButton)

            tDelay += tDelayInc
        else: self._storeButton = None


        if not self._inGame and self._haveQuitButton:
            h,v,scale = positions[pIndex]
            pIndex += 1
            self._quitButton = quitButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=useAutoSelect,position=(h - buttonWidth*0.5*scale,v),size=(buttonWidth,buttonHeight),scale=scale,
                                label = R.quitText if 'Mac' in bs.getEnvironment()['userAgentString'] else R.exitGameText,onActivateCall=self._quit,transitionDelay=tDelay)

            # scattered eggs on easter
            if bsInternal._getAccountMiscReadVal('easter',False):
                iconSize = 30
                iw = bs.imageWidget(parent=self._rootWidget,position=(h - iconSize*0.5+25,v+buttonHeight*scale-iconSize*0.24+1.5),transitionDelay=tDelay,
                                    size=(iconSize,iconSize),
                                    texture=bs.getTexture('egg1'),tiltScale=0.0)
            
            
            #if bsInternal._isOuyaBuild() or _bs._isRunningOnFireTV():
            bs.containerWidget(edit=self._rootWidget,cancelButton=quitButton)
            tDelay += tDelayInc
        else:
            self._quitButton = None

            # if we're not in-game, have no quit button, and this is android, we want back presses to quit our activity
            if not self._inGame and not self._haveQuitButton and 'android' in bs.getEnvironment()['userAgentString']:
                bs.containerWidget(edit=self._rootWidget,onCancelCall=bs.Call(QuitWindow,swish=True,back=True))

    def _quit(self):
        QuitWindow(originWidget=self._quitButton)
        
    def _demoMenuPress(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = KioskWindow(transition='inLeft').getRootWidget()
        
    def _showAccountWindow(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = AccountWindow(originWidget=self._gcButton).getRootWidget()

    def _onStorePressed(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = StoreWindow(originWidget=self._storeButton).getRootWidget()

    def _confirmEndGame(self):
        # FIXME - currently we crash calling this on client-sessions
        # if bsInternal._getForegroundHostSession() == None:
        #     bs.screenMessage("FIXME - need to replace this with 'disconnect' button or whatnot..")
        #     return
        
        # select cancel by default; this occasionally gets called by accident in a fit of button mashing
        # and this will help reduce damage
        ConfirmWindow(self._R.exitToMenuText,self._endGame,cancelIsSelected=True)

    def _confirmEndReplay(self):
        # select cancel by default; this occasionally gets called by accident in a fit of button mashing
        # and this will help reduce damage
        ConfirmWindow(self._R.exitToMenuText,self._endGame,cancelIsSelected=True)
        
    def _confirmLeaveParty(self):
        
        # select cancel by default; this occasionally gets called by accident in a fit of button mashing
        # and this will help reduce damage
        ConfirmWindow(self._R.leavePartyConfirmText,self._leaveParty,cancelIsSelected=True)

    def _leaveParty(self):
        bsInternal._disconnectFromHost()
        
    def _endGame(self):

        if not self._rootWidget.exists(): return
        
        bsUtils.stopStressTest() # stops any in-progress stress-testing
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

        # if we're in a host-session, tell them to end
        # this lets them tear themselves down gracefully..
        hostSession = bsInternal._getForegroundHostSession()
        if hostSession is not None:

            # kick off a little transaction so we'll hopefully have all the latest account state when we get back to the menu
            bsInternal._addTransaction({'type':'END_SESSION','sType':str(type(hostSession))})
            bsInternal._runTransactions()

            hostSession.end()

        # otherwise just force the issue..
        else:
            import bsMainMenu
            bs.pushCall(bs.Call(bsInternal._newHostSession,bsMainMenu.MainMenuSession))

    def _leave(self):
        if self._inputPlayer is not None and self._inputPlayer.exists():
            self._inputPlayer.removeFromGame()
        elif self._connectedToRemotePlayer:
            if self._inputDevice.exists():
                self._inputDevice.removeRemotePlayerFromGame()
        self._resume()

    def _credits(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = CreditsWindow(originWidget=self._creditsButton).getRootWidget()

    def _howToPlay(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = HelpWindow(mainMenu=True,originWidget=self._howToPlayButton).getRootWidget()

    def _settings(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = SettingsWindow(originWidget=self._settingsButton).getRootWidget()

    def _resumeAndCall(self,c):
        self._resume()
        c()

    def _doGameServicePress(self):
        self._saveState()
        bsInternal._showOnlineScoreUI()

    def _saveState(self):
        # dont do this for the in-game menu..
        if self._inGame: return
        global _gMainMenuSelection
        #s = bs.getWidgetSelectedChild(self._rootWidget)
        s = self._rootWidget.getSelectedChild()
        if s == self._startButton: _gMainMenuSelection = 'Start'
        elif s == self._gatherButton: _gMainMenuSelection = 'Gather'
        elif s == self._watchButton: _gMainMenuSelection = 'Watch'
        elif s == self._howToPlayButton: _gMainMenuSelection = 'HowToPlay'
        elif s == self._creditsButton: _gMainMenuSelection = 'Credits'
        elif s == self._settingsButton: _gMainMenuSelection = 'Settings'
        elif s == self._gcButton: _gMainMenuSelection = 'GameService'
        elif s == self._storeButton: _gMainMenuSelection = 'Store'
        elif s == self._quitButton: _gMainMenuSelection = 'Quit'
        elif s == self._demoMenuButton: _gMainMenuSelection = 'DemoMenu'
        else:
            print 'unknown widget in main menu store selection:'
            _gMainMenuSelection = 'Start'
        
    def _restoreState(self):
        # dont do this for the in-game menu..
        if self._inGame: return
        global _gMainMenuSelection
        try: selName = _gMainMenuSelection
        except Exception: selName = 'Start'
        if selName == 'HowToPlay': sel = self._howToPlayButton
        elif selName == 'Gather': sel = self._gatherButton
        elif selName == 'Watch': sel = self._watchButton
        elif selName == 'Credits': sel = self._creditsButton
        elif selName == 'Settings': sel = self._settingsButton
        elif selName == 'GameService': sel = self._gcButton
        elif selName == 'Store': sel = self._storeButton
        elif selName == 'Quit': sel = self._quitButton
        elif selName == 'DemoMenu': sel = self._demoMenuButton
        else: sel = self._startButton
        if sel is not None: bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        

    def _gatherPress(self):

        # we disallow net-play stuff if package mods are enabled
        # (that would cause lots of problems with clients having different assets from eachother)
        if bsUtils.gAllowingPackageMods:
            bs.screenMessage(bs.getResource('packageModsEnabledErrorText'))
            bs.playSound(bs.getSound('error'))
            return
        
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = GatherWindow(originWidget=self._gatherButton).getRootWidget()
        
    def _watchPress(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = WatchWindow(originWidget=self._watchButton).getRootWidget()
        #uiGlobals['mainMenuWindow'] = TestWindow(transition='inRight').getRootWidget()

        # env = bs.getEnvironment()
        # if env['platform'] == 'android':
        #     bs.screenMessage("This will let you watch and share replays (coming soon)..",color=(1,0,0))
        #     return
        # else:
        
        # global gMainWindow
        # gMainWindow = None
        # try:
        #     bsInternal._newReplaySession()
        # except Exception:
        #     import bsMainMenu
        #     bs.printException("exception running replay session")
        #     # drop back into a main menu session..
        #     bsInternal._newHostSession(bsMainMenu.MainMenuSession)
        
    def _playPress(self):
        self._saveState()
        global gShouldAskToMakeProfile
        # if we have no profiles, lets ask if they wanna make one
        #if gShouldAskToMakeProfile and ('Player Profiles' not in bs.getConfig() or len(bs.getConfig()['Player Profiles']) == 0):
        # if False:
        #     AskToMakeProfileWindow()
        # else:
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        uiGlobals['mainMenuWindow'] = PlayWindow(originWidget=self._startButton).getRootWidget()

    def _resume(self):

        resume()

        if self._rootWidget.exists():
            bs.containerWidget(edit=self._rootWidget, transition='outRight')
            
        uiGlobals['mainMenuWindow'] = None

        # if there's callbacks waiting for this window to go away, call them
        for call in gMainMenuResumeCallbacks: call()
        del gMainMenuResumeCallbacks[:]


class ConfigErrorWindow(Window):

    def __init__(self):

        self._configFilePath = bs.getEnvironment()['configFilePath']
        width = 800
        self._rootWidget = bs.containerWidget(size=(width,300),transition='inRight')
        padding = 20
        t = bs.textWidget(parent=self._rootWidget,position=(padding,220),size=(width-2*padding,100-2*padding),
                          hAlign="center",vAlign="top", scale=0.73,
                          text="Error reading BombSquad config file:\n\n\nCheck the console (press ~ twice) for details.\n\nWould you like to quit and try to fix it by hand\nor overwrite it with defaults?\n\n(high scores, player profiles, etc will be lost if you overwrite)")
        t2 = bs.textWidget(parent=self._rootWidget,position=(padding,198),size=(width-2*padding,100-2*padding),
                          hAlign="center",vAlign="top", scale=0.5,
                          text=self._configFilePath)
        quitButton = bs.buttonWidget(parent=self._rootWidget,position=(35,30),size=(240,54),label="Quit and Edit",onActivateCall=self._quit)
        b = bs.buttonWidget(parent=self._rootWidget,position=(width-370,30),size=(330,54),label="Overwrite with Defaults",onActivateCall=self._defaults)
        bs.containerWidget(edit=self._rootWidget,cancelButton=quitButton,selectedChild=quitButton)

    def _quit(self):
        bs.realTimer(1,self._editAndQuit)
        bsInternal._lockAllInput()

    def _editAndQuit(self):
        bsInternal._openFileExternally(self._configFilePath)
        bs.realTimer(100,bs.quit)

    def _defaults(self):
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        bs.playSound(bs.getSound('gunCocking'))
        bs.screenMessage("settings reset.",color=(1,1,0))
        # at this point settings are already set; lets just commit them to disk..
        bs.writeConfig(force=True)

class SpecialOfferWindow(Window):

    def __init__(self,offer,transition='inRight'):

        # first thing: if we're offering pro or an IAP, see if we have a price for it.
        # if not, abort and go into zombie mode (the user should never see us that way)
        if offer['item'] == 'pro':
            realPrice = bsInternal._getPrice('pro_sale')
            zombie = True if realPrice is None else False
        elif type(offer['price']) is str: # a string price implies IAP id
            realPrice = bsInternal._getPrice(offer['price'])
            zombie = True if realPrice is None else False
        else:
            realPrice = None
            zombie = False
        if realPrice is None: realPrice = '?'
            
        # if we wanted a real price but didn't find one, go zombie..
        if zombie:
            return
    
        # this can pop up suddenly, so lets block input for 1 second...
        bsInternal._lockAllInput()
        bs.realTimer(1000,bsInternal._unlockAllInput)

        bs.playSound(bs.getSound('ding'))
        bs.realTimer(300,lambda: bs.playSound(bs.getSound('ooh')))

        self._offer = copy.deepcopy(offer)
        
        self._width = width = 580
        self._height = height = 520

        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scale=1.25 if gSmallUI else 1.15 if gMedUI else 1.0,
                                              stackOffset=(0,-15) if gSmallUI else (0,0))

        self._isBundleSale = False
        
        try:
            if offer['item'] == 'pro':
                originalPriceStr = bsInternal._getPrice('pro')
                if originalPriceStr is None: originalPriceStr = '?'
                newPriceStr = bsInternal._getPrice('pro_sale')
                if newPriceStr is None: newPriceStr = '?'
                percentOffText = ''
            else:
                # if the offer includes bonus tickets it's a bundle-sale
                if 'bonusTickets' in offer and offer['bonusTickets'] is not None: self._isBundleSale = True
                originalPrice = bsInternal._getAccountMiscReadVal('price.'+offer['item'],9999)
                newPrice = offer['price']
                tChar = bs.getSpecialChar('ticket')
                originalPriceStr = tChar+str(originalPrice)
                newPriceStr = tChar+str(newPrice)
                percentOff = int(round(100.0 - (float(newPrice)/originalPrice)*100.0))
                percentOffText = ' '+bs.getResource('store.salePercentText').replace('${PERCENT}',str(percentOff))
        except Exception:
            originalPriceStr = newPriceStr = '?'
            percentOffText = ''

        # if its a bundle sale, change the title
        if self._isBundleSale:
            saleText = bs.getResource('store.saleBundleText',fallback='store.saleText')
        else:
            saleText = bs.getResource('store.saleExclaimText',fallback='store.saleText')
        
        
        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-40),
                      size=(0,0),text=saleText+((' '+bs.getResource('store.oneTimeOnlyText')) if self._offer['oneTimeOnly'] else '') + percentOffText,
                      hAlign='center',vAlign='center',maxWidth=self._width*0.9-220,
                      scale=1.4,
                      color=(0.3,1,0.3))
        
        self._flashOn = False
        self._flashingTimer = bs.Timer(50,bs.WeakCall(self._flashCycle),repeat=True,timeType='real')
        bs.realTimer(600,bs.WeakCall(self._stopFlashing))

        size = _getStoreItemDisplaySize(offer['item'])
        display = {}
        _instantiateStoreItemDisplay(offer['item'],display,
                                     parentWidget=self._rootWidget,
                                     bPos=(self._width*0.5-size[0]*0.5+10 - ((size[0]*0.5+30) if self._isBundleSale else 0),
                                           self._height*0.5-size[1]*0.5+20 + (20 if self._isBundleSale else 0)),
                                     bWidth=size[0],bHeight=size[1],
                                     button=False if self._isBundleSale else True)
        # wire up the parts we need..
        if self._isBundleSale:
            self._plusText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5+50),
                                           size=(0,0),text='+',
                                           hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                           scale=1.4,
                                           color=(0.5,0.5,0.5))
            self._plusTickets = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5+120,self._height*0.5+50),
                                           size=(0,0),text=bs.getSpecialChar('ticketBacking')+str(offer['bonusTickets']),
                                           hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                           scale=2.5,
                                           color=(1,0.5,0))
            self._priceText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,150),
                                            size=(0,0),text=realPrice,
                                            hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                            scale=1.4,
                                            color=(1,0.5,0))
        else:
            bs.buttonWidget(edit=display['button'],onActivateCall=self._purchase)
            bs.imageWidget(edit=display['priceSlashWidget'],opacity=1.0)
            bs.textWidget(edit=display['priceWidgetLeft'],text=originalPriceStr)
            bs.textWidget(edit=display['priceWidgetRight'],text=newPriceStr)
            
            
        # add ticket button only if this is ticket-purchasable
        if offer['price'] is not None and type(offer['price']) is int:
            self._getTicketsButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-125,self._height-68),
                                                         size=(90,55),scale=1.0,
                                                         buttonType='square',
                                                         color=(0.7,0.5,0.85),
                                                         textColor=(1,0.5,0),
                                                         autoSelect=True,
                                                         label=bs.getResource('getTicketsWindow.titleText'),
                                                         onActivateCall=self._onGetMoreTicketsPress)

            self._ticketTextUpdateTimer = bs.Timer(1000,bs.WeakCall(self._updateTicketsText),timeType='real',repeat=True)
            self._updateTicketsText()

        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        
        self._cancelButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                 position=(50,40) if self._isBundleSale else (self._width*0.5-75,40),
                                                 size=(150,60),scale=1.0,
                                                 onActivateCall=self._cancel,
                                                 autoSelect=True,
                                                 label=bs.getResource('noThanksText'))
        if self._isBundleSale:
            self._purchaseButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                       position=(self._width-200,40),
                                                       size=(150,60),scale=1.0,
                                                       onActivateCall=self._purchase,
                                                       autoSelect=True,
                                                       label=bs.getResource('store.purchaseText'))
            
        bs.containerWidget(edit=self._rootWidget,
                           cancelButton=self._cancelButton,
                           startButton=self._purchaseButton if self._isBundleSale else None,
                           selectedChild=self._purchaseButton if self._isBundleSale else display['button'])

    def _stopFlashing(self):
        self._flashingTimer = None
        bs.textWidget(edit=self._titleText,
                      color=(0.3,1,0.3))

    def _flashCycle(self):
        if not self._rootWidget.exists(): return
        self._flashOn = not self._flashOn
        bs.textWidget(edit=self._titleText,
                      color=(0.3,1,0.3) if self._flashOn else (1,0.5,0))
        
    def _update(self):

        canDie = False
        
        # we go away if we see that our target item is owned..
        if self._offer['item'] == 'pro':
            if bsUtils._havePro():
                canDie = True
        else:
            if bsInternal._getPurchased(self._offer['item']): canDie = True
            
        if canDie:
            bs.containerWidget(edit=self._rootWidget,transition='outLeft')
                
        
    def _updateTicketsText(self):
        if not self._rootWidget.exists(): return
        if bsInternal._getAccountState() == 'SIGNED_IN':
            s = bs.getSpecialChar('ticket')+str(bsInternal._getAccountTicketCount())
        else:
            s = bs.getResource('getTicketsWindow.titleText')
        bs.buttonWidget(edit=self._getTicketsButton,label=s)

    def _onGetMoreTicketsPress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        window = GetTicketsWindow(modal=True).getRootWidget()
        
    
    def _purchase(self):
        
        if self._offer['item'] == 'pro':
            bsInternal._purchase('pro_sale')
            #bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        elif self._isBundleSale:
            bsInternal._purchase(self._offer['price']) # with bundle sales, the price is the name of the IAP
        else:
            try: ticketCount = bsInternal._getAccountTicketCount()
            except Exception: ticketCount = None
            if ticketCount is not None and ticketCount < self._offer['price']:
                showGetTicketsPrompt()
                bs.playSound(bs.getSound('error'))
                return
            def doIt():
                bsInternal._inGamePurchase('offer:'+str(self._offer['id']),self._offer['price'])
                #bs.containerWidget(edit=self._rootWidget,transition='outLeft')
            bs.playSound(bs.getSound('swish'))
            ConfirmWindow(bs.getResource('store.purchaseConfirmText').replace('${ITEM}',_getStoreItemNameTranslated(self._offer['item'])),width=400,height=120,
                          action=doIt,okText=bs.getResource('store.purchaseText',fallback='okText'))
        
    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        

class PurchaseWindow(Window):

    def __init__(self,items,transition='inRight'):

        if len(items) != 1: raise Exception('expected exactly 1 item')
        
        self._items = list(items)
        
        self._width = width = 580
        self._height = height = 520

        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scale=1.25 if gSmallUI else 1.15 if gMedUI else 1.0,
                                              stackOffset=(0,-15) if gSmallUI else (0,0))

        
        self._isDouble = False
        
        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-40),
                      size=(0,0),text=bs.getResource('unlockThisText', fallback='unlockThisInTheStoreText'),
                      hAlign='center',vAlign='center',maxWidth=self._width*0.9-120,
                      scale=1.4,
                      color=(1,0.8,0.3,1))
        
        size = _getStoreItemDisplaySize(items[0])
        display = {}
        _instantiateStoreItemDisplay(items[0],display,
                                     parentWidget=self._rootWidget,
                                     bPos=(self._width*0.5-size[0]*0.5+10 - ((size[0]*0.5+30) if self._isDouble else 0),
                                           self._height*0.5-size[1]*0.5+30 + (20 if self._isDouble else 0)),
                                     bWidth=size[0],bHeight=size[1],
                                     button=False)
        # wire up the parts we need..
        if self._isDouble:
            self._plusText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5+50),
                                           size=(0,0),text='+',
                                           hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                           scale=1.4,
                                           color=(0.5,0.5,0.5))
            self._plusTickets = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5+120,self._height*0.5+50),
                                           size=(0,0),text=bs.getSpecialChar('ticketBacking')+str(offer['bonusTickets']),
                                           hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                           scale=2.5,
                                           color=(1,0.5,0))
            self._priceText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,150),
                                            size=(0,0),text=realPrice,
                                            hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                            scale=1.4,
                                            color=(1,0.5,0))
        else:
            if self._items == ['pro']:
                priceStr = bsInternal._getPrice(self._items[0])
            else:
                price = self._price = bsInternal._getAccountMiscReadVal('price.'+str(items[0]),-1)
                priceStr = bs.getSpecialChar('ticket')+str(price)
            self._priceText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,150),
                                            size=(0,0),text=priceStr,
                                            hAlign='center',vAlign='center',maxWidth=self._width*0.9,
                                            scale=1.4,
                                            color=(1,0.5,0))

        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        
        self._cancelButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                 position=(50,40),
                                                 size=(150,60),scale=1.0,
                                                 onActivateCall=self._cancel,
                                                 autoSelect=True,
                                                 label=bs.getResource('cancelText'))
        self._purchaseButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                   position=(self._width-200,40),
                                                   size=(150,60),scale=1.0,
                                                   onActivateCall=self._purchase,
                                                   autoSelect=True,
                                                   label=bs.getResource('store.purchaseText'))
            
        bs.containerWidget(edit=self._rootWidget,
                           cancelButton=self._cancelButton,
                           startButton=self._purchaseButton,
                           selectedChild=self._purchaseButton)

    def _update(self):

        canDie = False
        
        # we go away if we see that our target item is owned..
        if self._items == ['pro']:
            if bsUtils._havePro():
                canDie = True
        else:
            if bsInternal._getPurchased(self._items[0]): canDie = True
            
        if canDie:
            bs.containerWidget(edit=self._rootWidget,transition='outLeft')
                
    def _purchase(self):

        if self._items == ['pro']:
            bsInternal._purchase('pro')
        else:
            try: ticketCount = bsInternal._getAccountTicketCount()
            except Exception: ticketCount = None
            if ticketCount is not None and ticketCount < self._price:
                showGetTicketsPrompt()
                bs.playSound(bs.getSound('error'))
                return
            def doIt():
                bsInternal._inGamePurchase(self._items[0],self._price)
            bs.playSound(bs.getSound('swish'))
            doIt()
        
    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        
        
gSpecialOffer = None
def _showOffer():
    try:
        global gSpecialOffer
        if gSpecialOffer is not None:
            with bs.Context('UI'):
                if gSpecialOffer['item'] == 'rating':
                    askForRating()
                else:
                    offer = gSpecialOffer
                    def doIt():
                        try:
                            if offer['item'] == 'pro':
                                bsInternal._purchase('pro_sale')
                            else:
                                bsInternal._inGamePurchase('offer:'+str(offer['id']),offer['price'])
                        except Exception:
                            bs.printException('Error running special offer')
                    SpecialOfferWindow(gSpecialOffer)
                    
            gSpecialOffer = None
            return True
    except Exception:
        bs.printException('Error showing offer')
        
    return False

def askForRating():
    env = bs.getEnvironment()
    platform = env['platform']
    subplatform = env['subplatform']
    if not (platform == 'mac' or (platform == 'android' and subplatform in ['google','cardboard'])): return
    width = 700
    height = 400
    spacing = 40
    d = bs.containerWidget(size=(width,height),transition='inRight',scale=1.6 if gSmallUI else 1.35 if gMedUI else 1.0)
    v = height - 50
    v -= spacing
    v -= 140
    w = bs.imageWidget(parent=d,position=(width/2-100,v+10),size=(200,200),
                       texture=bs.getTexture("cuteSpaz"))
    t = bs.textWidget(parent=d,position=(15,v-55),size=(width-30,30),
                      color=gInfoTextColor,
                      text=bs.getResource('pleaseRateText').replace('${APP_NAME}',bs.getResource('titleText')),
                      maxWidth=width*0.95,maxHeight=130,
                      scale=0.85,
                      hAlign="center",vAlign="center")

    def doRating():

        # doing this in a timer seems to keep bombsquad from maintaining focus
        if platform == 'android':
            if subplatform == 'google': url = 'market://details?id=net.froemling.bombsquad'
            else: url = 'market://details?id=net.froemling.bombsquadcb'
        else: url = 'macappstore://itunes.apple.com/app/id416482767?ls=1&mt=12'

        bs.openURL(url)
        bs.containerWidget(edit=d,transition='outLeft')

    b = bs.buttonWidget(parent=d,position=(60,20),size=(200,60),
                        label=bs.getResource('wellSureText'),autoSelect=True,
                        onActivateCall=doRating)

    def close():
        bs.containerWidget(edit=d,transition='outLeft')

    b = bs.buttonWidget(parent=d,position=(width - 270,20),size=(200,60),
                        label=bs.getResource('noThanksText'),autoSelect=True,
                        onActivateCall=close)
    bs.containerWidget(edit=d,cancelButton=b,selectedChild=b)
    return d

def runPostLaunchStuff():

    env = bs.getEnvironment()
    bsConfig = bs.getConfig()

    # first off, if there's a leftover log file, attempt to upload
    # it to the server and/or get rid of it..
    try:
        import ast
        if os.path.exists(bsInternal._getLogFilePath()):
            f = open(bsInternal._getLogFilePath())
            info = ast.literal_eval(f.read())
            f.close()
            doSend = bsUtils._shouldSubmitDebugInfo()

            if doSend:
                def response(data):
                    # non-None response means we were succesful; lets kill it.
                    if data is not None: os.remove(bsInternal._getLogFilePath())
                bsUtils.serverPut('bsLog', info, response)
            else:
                # if they dont want logs uploaded just kill it
                os.remove(bsInternal._getLogFilePath())
    except Exception:
        bs.printException('Error handling leftover log file')


    # notify the user if we're using custom system scripts:
    if env['systemScriptsDirectory'] != 'data/scripts':
        bs.screenMessage("Using custom system scripts...",color=(0,1,0))

    # (only do this stuff if our config file is healthy so we dont
    # overwrite a broken one or whatnot and wipe out data)
    if not bsUtils.gConfigFileIsHealthy:
        ua = env['userAgentString']
        if 'Mac' in ua or 'linux' in ua or 'windows' in ua:
            ConfigErrorWindow()
            return
        else:
            # for now on other systems we just overwrite the bum config
            # at this point settings are already set; lets just commit them to disk..
            bs.writeConfig(force=True)

    # if we're using a non-default playlist lets go ahead and get
    # our music-player going since it may hitch
    # (better while we're faded out than later)
    try:
        if 'Soundtrack' in bsConfig and bsConfig['Soundtrack'] not in['__default__','Default Soundtrack']:
            bsUtils.getMusicPlayer()
    except Exception:
        bs.printException('error prepping music-player')

    launchCount = bsConfig.get('launchCount', 0)
    launchCount += 1

    for key in ('lc14','lc14c','lc14146','lc14173'):
        bsConfig.setdefault(key,launchCount)
        
    # debugging - make note if we're using the local test server so we dont accidentally
    # leave it on in a release
    serverAddr = bsInternal._getServerAddress()
    if 'localhost' in serverAddr:
        bs.realTimer(2000,bs.Call(bs.screenMessage,"Note: using local server",(1,1,0)))
    elif 'test.' in serverAddr:
        bs.realTimer(2000,bs.Call(bs.screenMessage,"Note: using test server-module",(1,1,0)))

    gamePadConfigQueryDelay = 1000

    platform = env['platform']
    subplatform = env['subplatform']

    # ask if we can submit debug info
    try: canDebug = bsConfig['Submit Debug Info']
    except Exception: canDebug = True

    # update - just gonna enable this for now and put a disable
    # option in advanced settings or whatnot..
    forceTest3 = False

    # lets make a list of unconfigured joysticks so if we're sitting idle
    # we can ask the user to config them
    global gUntestedGamePads
    gUntestedGamePads += bsInternal._getConfigurableGamePads()

    # if there's any gamepads in there, set up our timer to go through them..
    if len(gUntestedGamePads) > 0:
        bs.realTimer(gamePadConfigQueryDelay,_setupGamePadConfigTimer)

    bsConfig['launchCount'] = launchCount

    # write out our config in a few seconds.. this delay gives a little time
    # for cloud settings to come in so we're less likely to inadvertantly overwrite cloud
    # values with stale old values of ours and stuff..
    bs.realTimer(5000,bs.writeConfig)

    # lets go ahead and scan our games to avoid hitches later
    bsUtils.getGameTypes()

    # migrate old setting to the new one..
    try:
        if bsInternal._isUsingInternalAccounts():
            if bsConfig.get('Test Account Sign In',False):
                del bsConfig['Test Account Sign In']
                bsConfig['Auto Account State'] = 'Test'
    except Exception:
        bs.printException('error migrating test account signin')

    # auto-sign-in to a test or local account in a moment if we're set to..
    def doAutoSignIn():
        if bsConfig.get('Auto Account State') == 'Test' and bsInternal._isUsingInternalAccounts():
            bsInternal._signIn('Test')
        elif bsConfig.get('Auto Account State') == 'Local':
            bsInternal._signIn('Local')
    bs.realTimer(1,doAutoSignIn)
        
    bsUtils._gRanPostLaunchStuff = True

    
def checkGamePadConfigs():
    " can be called during idle time to ask the user to configure any unconfigured joysticks "

    global gCanAskToConfigGamePads

    # go through the list until we find one we ask about or we have to stop asking
    while len(gUntestedGamePads) > 0 and gCanAskToConfigGamePads:
        
        gamepad = gUntestedGamePads.pop()

        # ok lets just ask for a button assignment for this joystick.. if we dont get anything
        # back lets ask the user if they want to configure it..
        try:
            getControllerValue(gamepad,"buttonJump",exceptionOnUnknown=True)
            known = True
        except Exception:
            known = False

        # in some cases we dont bother asking (if it looks like its a keyboard or a mouse that just happens
        # to be showing up as a joystick)
        ask = True
        try:
            name = gamepad.getName().lower()
            if any((s in name for s in ['mouse','keyboard','athome_remote','cec_input','alitv gamepad'])):
                ask = False
                
        except Exception,e:
            print 'EXC checking gp name',e
            ask = False

        # FIXME - if ask is false we should maybe still ask the server for the config
        if not known and ask:
            
            def askToConfig():
                try: name = gamepad.getName()
                except Exception:
                    name = None

                # COMPLETELY DISABLING THIS FOR NOW
                # ..there's just too many funky corner cases where this can pop up
                # at inopportune times or get hidden behind the main menu or whatnot
                # ..maybe can revisit later.
                return
            
                # only proceed if we can get its name
                if name is not None:
                    bs.playSound(bs.getSound('swish'))
                    # dont ask about more while we're configing this one..
                    global gCanAskToConfigGamePads
                    gCanAskToConfigGamePads = False

                    width = 600
                    height = 200
                    spacing = 40
                    d = bs.containerWidget(scale=1.8 if gSmallUI else 1.4 if gMedUI else 1.0,
                                           size=(width,height),transition='inRight')

                    v = height - 60
                    t = bs.textWidget(parent=d,position=(15,v),size=(width-30,30),
                                      color=gInfoTextColor,
                                      text=bs.getResource('unconfiguredControllerDetectedText'),
                                      scale=0.8,
                                      hAlign="center",vAlign="top")
                    v -= 30
                    t = bs.textWidget(parent=d,position=(15,v),size=(width-30,30),
                                      color=(1,1,1,1.0),
                                      text=name,
                                      hAlign="center",vAlign="top")
                    v -= 30
                    t = bs.textWidget(parent=d,position=(15,v),size=(width-30,30),
                                      color=gInfoTextColor,
                                      text=bs.getResource('configureItNowText'),
                                      scale=0.8,
                                      hAlign="center",vAlign="top")

                    def doConfigure(gamepad):
                        bs.containerWidget(edit=d,transition='outLeft')
                        GamePadConfigWindow(gamepad,isMainMenu=False)

                    b = bs.buttonWidget(parent=d,position=(20,20),size=(200,60),
                                        label=bs.getResource('configureText'),
                                        onActivateCall=bs.Call(doConfigure,gamepad))

                    def close():
                        bs.containerWidget(edit=d,transition='outLeft')

                        # if they dont wanna configure now, lets cancel all..
                        global gUntestedGamePads
                        gUntestedGamePads = []

                        # ok can go back to asking now..
                        global gCanAskToConfigGamePads
                        gCanAskToConfigGamePads = True

                    b = bs.buttonWidget(parent=d,position=(width - 230,20),size=(200,60),
                                        label=bs.getResource('notNowText'),
                                        onActivateCall=close)

            def cb(data):
                global gCanAskToConfigGamePads
                gCanAskToConfigGamePads = True

                try: name = gamepad.getName()
                except Exception: name = None

                haveConfig = False
                
                # if data and 'config' in data and data['config'] is not None and name is not None:
                if data:
                    if data.get('config') is not None and name is not None:
                        # if there's currently no default config entry, write this one
                        configLoc = getConfigLocationForInputDevice(gamepad,default=True)
                        configDict = configLoc[0][configLoc[1]]
                        if len(configDict) == 0:
                            configLoc[0][configLoc[1]] = copy.deepcopy(data['config'])
                            haveConfig = True
                            bs.applySettings()
                            bs.writeConfig()
                    elif name is not None:
                        # server got our request but didn't have a config for us;
                        # make note locally so we don't keep asking about it
                        configChecks = bs.getConfig().setdefault('Controller Config Checks',{})
                        configChecks[name] = {}
                        bs.writeConfig()
                        
                # finally if we still have no config, possibly ask the user..
                if not haveConfig:
                    askToConfig()

            # if we can get its name, ask the server about it
            # we include our input-map-hash so that differently mapped systems
            # will return different sets of results
            try: name = gamepad.getName()
            except Exception: name = None
            if name is not None:
                configChecks = bs.getConfig().get('Controller Config Checks',{})
                if name not in configChecks:
                    gCanAskToConfigGamePads = False # lock while waiting for response
                    bsUtils.serverGet('controllerConfig',{'ua':bs.getEnvironment()['userAgentString'],'name':name,'inputMapHash':getInputMapHash(gamepad)},callback=cb)


    # ok, lastly, if there's no more gamepads to ask about, lets kill our timer
    if len(gUntestedGamePads) == 0:
        global gGamePadConfigQueryTimer
        gGamePadConfigQueryTimer = None

def _setupGamePadConfigTimer():
    # make/rename a timer to periodically ask about gamepads until none are left
    global gGamePadConfigQueryTimer
    gGamePadConfigQueryTimer = bs.Timer(1000,checkGamePadConfigs,repeat=True,timeType='real')


# hmm should we generalize this a bit more?...
# (ie; any input device; not just configurable gamepads)
def _onConfigurableGamePadConnected(inputDevice):
    # put this on the list so we can offer to config it if its not..
    gUntestedGamePads.append(inputDevice)
    _setupGamePadConfigTimer()


class KioskWindow(Window):
    def __init__(self,transition='inRight'):
        
        self._width = 720
        self._height = 340
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              onCancelCall=bs.Call(QuitWindow,swish=True,back=True),
                                              background=False,stackOffset=(0,-130))

        self._R = bs.getResource('kioskWindow')

        # alter some default behavior when going through this menu..
        bsUtils.gRunningKioskModeGame = True
        
        # lets reset all random player names every time we hit the main menu
        bsInternal._resetRandomPlayerNames()

        # and achievements.. (at least locally)
        bs.getConfig()['Achievements'] = {}
        
        global gDidMenuIntro
        tDelayBase = 0
        tDelayScale = 0
        if gDidMenuIntro == False:
            tDelayBase = 1000
            tDelayScale = 1.0

        modelOpaque = bs.getModel('levelSelectButtonOpaque')
        modelTransparent = bs.getModel('levelSelectButtonTransparent')
        maskTex = bs.getTexture('mapPreviewMask')

        yExtra = 130
        bWidth = 250
        bHeight = 200
        bSpace = 280
        bV = 80+yExtra
        labelHeight = 130+yExtra
        imgWidth = 180
        imgV = 158+yExtra
        
        tDelay = tDelayBase+tDelayScale*1300
        bs.textWidget(parent=self._rootWidget,size=(0,0),position=(self._width*0.5,self._height+yExtra-44),
                      transitionDelay=tDelay,text=self._R.singlePlayerExamplesText,flatness=1.0,
                      scale=1.2,hAlign='center',vAlign='center',shadow=1.0)
        h = self._width*0.5-bSpace
        tDelay = tDelayBase+tDelayScale*700
        self._b1 = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,bHeight),
                            onActivateCall=bs.Call(self._doGame,'easy'),
                            transitionDelay=tDelay,position=(h-bWidth*0.5,bV),label='',buttonType='square')
        bs.textWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                      size=(0,0),position=(h,labelHeight),maxWidth=bWidth*0.7,
                      text=self._R.easyText,scale=1.3,hAlign='center',vAlign='center')
        b = bs.imageWidget(parent=self._rootWidget,drawController=b,
                           size=(imgWidth,0.5*imgWidth),transitionDelay=tDelay,
                           position=(h-imgWidth*0.5,imgV),
                           texture=bs.getTexture('doomShroomPreview'),
                           modelOpaque=modelOpaque,
                           modelTransparent=modelTransparent,
                           maskTexture=maskTex)
        h = self._width*0.5
        tDelay = tDelayBase+tDelayScale*650
        self._b2 = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,bHeight),
                            onActivateCall=bs.Call(self._doGame,'medium'),
                            position=(h-bWidth*0.5,bV),label='',buttonType='square',transitionDelay=tDelay)
        bs.textWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                      size=(0,0),position=(h,labelHeight),maxWidth=bWidth*0.7,
                      text=self._R.mediumText,scale=1.3,hAlign='center',vAlign='center')
        b = bs.imageWidget(parent=self._rootWidget,drawController=b,
                           size=(imgWidth,0.5*imgWidth),transitionDelay=tDelay,
                           position=(h-imgWidth*0.5,imgV),
                           texture=bs.getTexture('footballStadiumPreview'),
                           modelOpaque=modelOpaque,
                           modelTransparent=modelTransparent,
                           maskTexture=maskTex)
        h = self._width*0.5+bSpace
        tDelay = tDelayBase+tDelayScale*600
        self._b3 = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,bHeight),
                            onActivateCall=bs.Call(self._doGame,'hard'),
                            transitionDelay=tDelay,position=(h-bWidth*0.5,bV),label='',buttonType='square')
        bs.textWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                      size=(0,0),position=(h,labelHeight),maxWidth=bWidth*0.7,
                      text='Hard',scale=1.3,hAlign='center',vAlign='center')
        b = bs.imageWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                           size=(imgWidth,0.5*imgWidth),
                           position=(h-imgWidth*0.5,imgV),
                           texture=bs.getTexture('courtyardPreview'),
                           modelOpaque=modelOpaque,
                           modelTransparent=modelTransparent,
                           maskTexture=maskTex)
        tDelayBase = 0
        tDelayScale = 0
        if gDidMenuIntro == False:
            tDelayBase = 1500
            tDelayScale = 1.0
            gDidMenuIntro = True
        
        yExtra = -115
        bWidth = 250
        bHeight = 200
        bSpace = 280
        bV = 80+yExtra
        labelHeight = 130+yExtra
        imgWidth = 180
        imgV = 158+yExtra
        
        tDelay = tDelayBase+tDelayScale*1300
        bs.textWidget(parent=self._rootWidget,size=(0,0),position=(self._width*0.5,self._height+yExtra-44),
                      transitionDelay=tDelay,text=self._R.versusExamplesText,flatness=1.0,
                      scale=1.2,hAlign='center',vAlign='center',shadow=1.0)
        h = self._width*0.5-bSpace
        tDelay = tDelayBase+tDelayScale*700
        self._b4 = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,bHeight),
                            onActivateCall=bs.Call(self._doGame,'ctf'),
                            transitionDelay=tDelay,position=(h-bWidth*0.5,bV),label='',buttonType='square')
        bs.textWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                      size=(0,0),position=(h,labelHeight),maxWidth=bWidth*0.7,
                      text=bs.translate('gameNames','Capture the Flag'),scale=1.3,hAlign='center',vAlign='center')
        b = bs.imageWidget(parent=self._rootWidget,drawController=b,
                           size=(imgWidth,0.5*imgWidth),transitionDelay=tDelay,
                           position=(h-imgWidth*0.5,imgV),
                           texture=bs.getTexture('bridgitPreview'),
                           modelOpaque=modelOpaque,
                           modelTransparent=modelTransparent,
                           maskTexture=maskTex)
        
        h = self._width*0.5
        tDelay = tDelayBase+tDelayScale*650
        self._b5 = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,bHeight),
                            onActivateCall=bs.Call(self._doGame,'hockey'),
                            position=(h-bWidth*0.5,bV),label='',buttonType='square',transitionDelay=tDelay)
        bs.textWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                      size=(0,0),position=(h,labelHeight),maxWidth=bWidth*0.7,
                      text=bs.translate('gameNames','Hockey'),scale=1.3,hAlign='center',vAlign='center')
        b = bs.imageWidget(parent=self._rootWidget,drawController=b,
                           size=(imgWidth,0.5*imgWidth),transitionDelay=tDelay,
                           position=(h-imgWidth*0.5,imgV),
                           texture=bs.getTexture('hockeyStadiumPreview'),
                           modelOpaque=modelOpaque,
                           modelTransparent=modelTransparent,
                           maskTexture=maskTex)
        h = self._width*0.5+bSpace
        tDelay = tDelayBase+tDelayScale*600
        self._b6 = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,bHeight),
                            onActivateCall=bs.Call(self._doGame,'epic'),
                            transitionDelay=tDelay,position=(h-bWidth*0.5,bV),label='',buttonType='square')
        bs.textWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                      size=(0,0),position=(h,labelHeight),maxWidth=bWidth*0.7,
                      text=self._R.epicModeText,scale=1.3,hAlign='center',vAlign='center')
        b = bs.imageWidget(parent=self._rootWidget,drawController=b,transitionDelay=tDelay,
                           size=(imgWidth,0.5*imgWidth),
                           position=(h-imgWidth*0.5,imgV),
                           texture=bs.getTexture('tipTopPreview'),
                           modelOpaque=modelOpaque,
                           modelTransparent=modelTransparent,
                           maskTexture=maskTex)
        bWidth = 150
        tDelay = tDelayBase+tDelayScale*1300
        self._b7 = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,size=(bWidth,50),
                                   color=(0.45,0.55,0.45),textColor=(0.7,0.8,0.7),
                                   position=(self._width+60,yExtra+(120 if gSmallUI else 100)),transitionDelay=tDelay,
                        label=self._R.fullMenuText,onActivateCall=self._doFullMenu)
        self._restoreState()

    def _restoreState(self):
        try: selName = gWindowStates[self.__class__.__name__]
        except Exception: selName = None
        if selName == 'b1': sel = self._b1
        elif selName == 'b2': sel = self._b2
        elif selName == 'b3': sel = self._b3
        elif selName == 'b4': sel = self._b4
        elif selName == 'b5': sel = self._b5
        elif selName == 'b6': sel = self._b6
        elif selName == 'b7': sel = self._b7
        else: sel = self._b1
        bs.containerWidget(edit=self._rootWidget,selectedChild=sel)

    def _saveState(self):
        sel = self._rootWidget.getSelectedChild()
        if sel == self._b1: selName = 'b1'
        elif sel == self._b2: selName = 'b2'
        elif sel == self._b3: selName = 'b3'
        elif sel == self._b4: selName = 'b4'
        elif sel == self._b5: selName = 'b5'
        elif sel == self._b6: selName = 'b6'
        elif sel == self._b7: selName = 'b7'
        else: selName = 'b1'
        gWindowStates[self.__class__.__name__] = selName
        
    def _doGame(self,mode):
        self._saveState()
        if mode in ['epic','ctf','hockey']:
            bsConfig = bs.getConfig()
            if 'Team Tournament Playlists' not in bsConfig: bsConfig['Team Tournament Playlists'] = {}
            if 'Free-for-All Playlists' not in bsConfig: bsConfig['Free-for-All Playlists'] = {}
            bsConfig['Show Tutorial'] = False
            if mode == 'epic':
                bsConfig['Free-for-All Playlists']['Just Epic Elim'] = [
                    {
                        'settings':{
                            'Epic Mode':1,
                            'Lives Per Player':1,
                            'Respawn Times':1.0,
                            'Time Limit':0,
                            'map':'Tip Top'
                        },
                        'type':'bsElimination.EliminationGame'
                    }
                ]
                bsConfig['Free-for-All Playlist Selection'] = 'Just Epic Elim'
                bsInternal._fadeScreen(False,time=250,endCall=bs.Call(bs.pushCall,bs.Call(bsInternal._newHostSession,bs.FreeForAllSession)))
            else:
                if mode == 'ctf':
                    bsConfig['Team Tournament Playlists']['Just CTF'] = [
                        {
                            'settings':{
                                'Epic Mode':False,
                                'Flag Idle Return Time':30,
                                'Flag Touch Return Time':0,
                                'Respawn Times':1.0,
                                'Score to Win':3,
                                'Time Limit':0,
                                'map':'Bridgit'
                            },
                            'type':'bsCaptureTheFlag.CTFGame'
                        }
                    ]
                    bsConfig['Team Tournament Playlist Selection'] = 'Just CTF'
                else:
                    bsConfig['Team Tournament Playlists']['Just Hockey'] = [
                        {
                            'settings':{
                                'Respawn Times':1.0,
                                'Score to Win':1,
                                'Time Limit':0,
                                'map':'Hockey Stadium'
                            },
                            'type':'bsHockey.HockeyGame'
                        }
                    ]
                    bsConfig['Team Tournament Playlist Selection'] = 'Just Hockey'
                bsInternal._fadeScreen(False,time=250,endCall=bs.Call(bs.pushCall,bs.Call(bsInternal._newHostSession,bs.TeamsSession)))
            bs.containerWidget(edit=self._rootWidget,transition='outLeft')
            return
        
        game = ('Default:Onslaught Training' if mode == 'easy'
                else 'Default:Rookie Football' if mode == 'medium'
                else 'Default:Uber Onslaught')
        bs.getConfig()['Selected Coop Game'] = game
        bs.writeConfig()
        if bsUtils._handleRunChallengeGame(game,force=True):
            bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        
    def _doFullMenu(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        global gDidMenuIntro
        gDidMenuIntro = True # prevent delayed transition-in
        uiGlobals['mainMenuWindow'] = MainMenuWindow().getRootWidget()

class LocalConnectFailMessageWindow(Window):
    def __init__(self):
        width = 670
        height = 270
        bs.playSound(bs.getSound('error'))
        self._rootWidget = bs.containerWidget(size=(width,height),transition='inRight')
        t = bs.textWidget(parent=self._rootWidget,position=(15,height-55),size=(width-30,30),
                          text=("Fatal Error:\n\n"
                                +"BombSquad is unable to connect to itself on socket port "+str(bsInternal._getGamePort())+".\n"
                                +"It may be getting blocked by security software such as 'Hands Off!'.\n\n"
                                +"Change your your settings to allow BombSquad to\n"
                                +"host connections on port "+str(bsInternal._getGamePort())+" and and try again.\n\n"
                                +"If this does not work, email support@froemling.net for help."),
                          color=(1,0.6,0.2,1),
                          scale=0.8,
                          hAlign="center",vAlign="top")
        b = bs.buttonWidget(parent=self._rootWidget,position=((width-160)/2,10),size=(160,50),label="Quit",onActivateCall=bs.quit)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

def _onDeviceMenuPress(device):
    inMainMenu = (uiGlobals['mainMenuWindow'] is not None and uiGlobals['mainMenuWindow'].exists())
    if not inMainMenu:
        bsInternal._setUIInputDevice(device)
        bs.playSound(bs.getSound('swish'))
        uiGlobals['mainMenuWindow'] = MainMenuWindow().getRootWidget()


def handleTelnetAccessRequest():

    class _TelnetAccessWindow(Window):

        def __init__(self):
            width = 400
            height = 100
            text = bs.getResource('telnetAccessText')

            self._rootWidget = bs.containerWidget(size=(width,height+40),transition='inRight',scale=1.7 if gSmallUI else 1.3 if gMedUI else 1.0)
            padding = 20
            t = bs.textWidget(parent=self._rootWidget,position=(padding,padding+33),size=(width-2*padding,height-2*padding),
                              hAlign="center",vAlign="top",text=text)
            b = bs.buttonWidget(parent=self._rootWidget,position=(20,20),size=(140,50),label=bs.getResource('denyText'),onActivateCall=self._cancel)
            bs.containerWidget(edit=self._rootWidget,cancelButton=b)
            bs.containerWidget(edit=self._rootWidget,selectedChild=b)

            b = bs.buttonWidget(parent=self._rootWidget,position=(width-155,20),size=(140,50),label=bs.getResource('allowText'),onActivateCall=self._ok)

        def _cancel(self):
            bs.containerWidget(edit=self._rootWidget,transition='outRight')
            bsInternal._setTelnetAccessEnabled(False)

        def _ok(self):
            bs.containerWidget(edit=self._rootWidget,transition='outLeft')
            bsInternal._setTelnetAccessEnabled(True)
            bs.screenMessage(bs.getResource('telnetAccessGrantedText'))

    _TelnetAccessWindow()


class ShowURLWindow(Window):
    "Gets called by BombSquad when it is unable to bring up a browser"

    def __init__(self,address):

        # on alibaba show qr codes; otherwise just print the url
        env = bs.getEnvironment()
        if env['platform'] == 'android' and env['subplatform'] == 'alibaba':
            self._width = 500
            self._height = 500
            self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition='inRight',scale=1.25 if gSmallUI else 1.25 if gMedUI else 1.25)
            self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.6,
                                                 label='',color=(0.6,0.5,0.6),
                                                 onActivateCall=self._done, autoSelect=True,
                                                 icon=bs.getTexture('crossOut'),iconScale=1.2)
            qrSize = 400
            iw2 = bs.imageWidget(parent=self._rootWidget,position=(self._width * 0.5 - qrSize*0.5,self._height * 0.5 - qrSize * 0.5),size=(qrSize, qrSize),
                                texture=bsInternal._getQRCodeTexture(address))
            bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)
            pass
        else:

            self._width = 800
            self._height = 200
            self._rootWidget = bs.containerWidget(size=(self._width,self._height+40),transition='inRight',scale=1.25 if gSmallUI else 1.25 if gMedUI else 1.25)
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-10),size=(0,0),
                              color=gTitleColor,hAlign="center",vAlign="center",text=bs.getResource('directBrowserToURLText'),maxWidth=self._width*0.95)
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5+29),size=(0,0),scale=1.3,
                              color=gInfoTextColor,hAlign="center",vAlign="center",text=address,maxWidth=self._width*0.95)
            buttonWidth = 200
            b = bs.buttonWidget(parent=self._rootWidget,position=(self._width*0.5-buttonWidth*0.5,20),size=(buttonWidth,65),label=bs.getResource('doneText'),onActivateCall=self._done)
            # we have no 'cancel' button but still want to be able to hit back/escape/etc to leave..
            bs.containerWidget(edit=self._rootWidget,selectedChild=b,startButton=b,onCancelCall=b.activate)
        
    def _done(self):
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

class GetTicketsWindow(Window):
        
    def __init__(self, transition='inRight', fromModalStore=False, modal=False, originWidget=None, storeBackLocation=None):

        bsInternal._setAnalyticsScreen('Get Tickets Window')

        self._transitioningOut = False
        self._storeBackLocation = storeBackLocation # ew.
        
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
            
        self._width = 800
        self._height = 480

        self._modal = modal
        self._fromModalStore = fromModalStore
        self._R = bs.getResource('getTicketsWindow')

        topExtra = 20 if gSmallUI else 0
        
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              color=(0.4,0.37,0.55),
                                              scale=1.63 if gSmallUI else 1.2 if gMedUI else 1.0,
                                              stackOffset=(0,-3) if gSmallUI else (0,0))

        backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(55,self._height-79),size=(140,60),scale=1.0,
                                         autoSelect=True,label=bs.getResource('doneText' if modal else 'backText'),
                                         buttonType='regular' if modal else 'back',
                                         onActivateCall=self._back)

        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-55),size=(0,0),
                          color=gTitleColor,scale=1.2,hAlign="center",vAlign="center",
                          text=self._R.titleText,maxWidth=290)

        if gDoAndroidNav and not modal:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(135,self._height-49))
        
        bSize = (220.0,180.0)
        bSize2 = (220,180)
        v = self._height - bSize[1] - 80
        spacing = 1

        self._adButton = None
        
        def _addButton(item,position,size,label,price=None,texName=None,texOpacity=1.0,texScale=1.0,enabled=True,textScale=1.0):
            b = bs.buttonWidget(parent=self._rootWidget,position=position,buttonType='square',size=size,label='',autoSelect=True,
                                color=None if enabled else (0.5,0.5,0.5),onActivateCall=(bs.Call(self._purchase,item) if enabled else self._disabledPress))
            t = bs.textWidget(parent=self._rootWidget,text=label,position=(position[0]+size[0]*0.5,position[1]+size[1]*0.3),
                              scale=textScale,
                              maxWidth=size[0]*0.75,size=(0,0),hAlign='center',vAlign='center',
                              drawController=b,
                              color=(0.7,0.9,0.7,1.0 if enabled else 0.2))
            if price is not None and enabled:
                bs.textWidget(parent=self._rootWidget,text=price,position=(position[0]+size[0]*0.5,position[1]+size[1]*0.17),
                              scale=0.7,
                              maxWidth=size[0]*0.75,size=(0,0),hAlign='center',vAlign='center',
                              drawController=b,
                              color=(0.4,0.9,0.4,1.0))
            if texName is not None:
                texSize=90.0*texScale
                i = bs.imageWidget(parent=self._rootWidget,texture=bs.getTexture(texName),position=(position[0]+size[0]*0.5-texSize*0.5,position[1]+size[1]*0.66-texSize*0.5),
                                   size=(texSize,texSize),drawController=b,opacity=texOpacity * (1.0 if enabled else 0.25))
            if item == 'ad':
                self._adButton = b
                self._adLabel = t
                self._adImage = i
                self._adTimeText = bs.textWidget(parent=self._rootWidget,text='1m 10s',position=(position[0]+size[0]*0.5,position[1]+size[1]*0.5),
                                                 scale=textScale * 1.2,
                                                 maxWidth=size[0]*0.85,size=(0,0),hAlign='center',vAlign='center',
                                                 drawController=b,
                                                 color=(0.4,0.9,0.4,1.0))
            return b

        cTxt = self._R.ticketsText

        c1Txt = cTxt.replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('tickets1Amount',50)))
        c2Txt = cTxt.replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('tickets2Amount',500)))
        c3Txt = cTxt.replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('tickets3Amount',1500)))
        c4Txt = cTxt.replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('tickets4Amount',5000)))
        c5Txt = cTxt.replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('tickets5Amount',15000)))

        h = 110
        
        # enable buttons if we have prices..
        tickets1Price = bsInternal._getPrice('tickets1')
        tickets2Price = bsInternal._getPrice('tickets2')
        tickets3Price = bsInternal._getPrice('tickets3')
        tickets4Price = bsInternal._getPrice('tickets4')
        tickets5Price = bsInternal._getPrice('tickets5')

        # TEMP
        # tickets1Price = '$0.99'
        # tickets2Price = '$4.99'
        # tickets3Price = '$9.99'
        # tickets4Price = '$19.99'
        # tickets5Price = '$49.99'

        c1b = _addButton('tickets2',enabled=(tickets2Price is not None),position=(self._width*0.5-spacing*1.5-bSize[0]*2.0+h,v),size=bSize,label=c2Txt,price=tickets2Price,texName='ticketsMore') # 0.99-ish
        c2b = _addButton('tickets3',enabled=(tickets3Price is not None),position=(self._width*0.5-spacing*0.5-bSize[0]*1.0+h,v),size=bSize,label=c3Txt,price=tickets3Price,texName='ticketRoll') # 4.99-ish
        v -= bSize[1]-5
        c3b = _addButton('tickets4',enabled=(tickets4Price is not None),position=(self._width*0.5-spacing*1.5-bSize[0]*2.0+h,v),size=bSize,label=c4Txt,price=tickets4Price,texName='ticketRollBig',texScale=1.2) # 9.99-ish
        c4b = _addButton('tickets5',enabled=(tickets5Price is not None),position=(self._width*0.5-spacing*0.5-bSize[0]*1.0+h,v),size=bSize,label=c5Txt,price=tickets5Price,texName='ticketRolls',texScale=1.2) # 19.99-ish

        env = bs.getEnvironment()
        self._enableAdButton = bsInternal._hasVideoAds()
        h = self._width*0.5+110
        v = self._height - bSize[1] - 115
        
        if self._enableAdButton:
            hOffs = 35
            bSize3 = (150,120)
            cdb = _addButton('ad',position=(h+hOffs,v),size=bSize3,
                             label=self._R.ticketsFromASponsorText.replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('sponsorTickets',5))),texName='ticketsMore',
                             enabled=self._enableAdButton,
                             texOpacity=0.6,texScale=0.7,textScale=0.7)
            bs.buttonWidget(edit=cdb,color=(0.65,0.5,0.7) if self._enableAdButton else (0.5,0.5,0.5))

            self._adFreeText = bs.textWidget(parent=self._rootWidget,text=self._R.freeText,position=(h+hOffs+bSize3[0]*0.5,v+bSize3[1]*0.5+25),
                                             size=(0,0),color=(1,1,0,1.0) if self._enableAdButton else (1,1,1,0.2),
                                             drawController=cdb,rotate=15,shadow=1.0,
                                             maxWidth=150,hAlign='center',vAlign='center',scale=1.0)
            tcYOffs = 0
            v -= 125
        else:
            v -= 20
            tcYOffs = 0

        if True:
            hOffs = 35
            bSize3 = (150,120)
            cdb = _addButton('appInvite',position=(h+hOffs,v),size=bSize3,
                             label=bs.getResource('gatherWindow.earnTicketsForRecommendingText').replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('sponsorTickets',5))),texName='ticketsMore',
                             enabled=True,
                             texOpacity=0.6,texScale=0.7,textScale=0.7)
            bs.buttonWidget(edit=cdb,color=(0.65,0.5,0.7))

            bs.textWidget(parent=self._rootWidget,text=self._R.freeText,position=(h+hOffs+bSize3[0]*0.5,v+bSize3[1]*0.5+25),
                          size=(0,0),color=(1,1,0,1.0),
                          drawController=cdb,rotate=15,shadow=1.0,
                          maxWidth=150,hAlign='center',vAlign='center',scale=1.0)
            tcYOffs = 0
            
        h = self._width-185
        v = self._height - 95+tcYOffs

        
        t1 = self._R.youHaveText.split('${COUNT}')[0].strip()
        t2 = self._R.youHaveText.split('${COUNT}')[-1].strip()
        
        bs.textWidget(parent=self._rootWidget,text=t1,position=(h,v),size=(0,0),color=(0.5,0.5,0.6),
                      maxWidth=200,hAlign='center',vAlign='center',scale=0.8)
        v -= 30
        self._ticketCountText = bs.textWidget(parent=self._rootWidget,position=(h,v),size=(0,0),color=(1.5,0.5,0.0),
                                              maxWidth=200,hAlign='center',vAlign='center',scale=1.6)
        v -= 30
        bs.textWidget(parent=self._rootWidget,text=t2,position=(h,v),size=(0,0),color=(0.5,0.5,0.6),
                      maxWidth=200,hAlign='center',vAlign='center',scale=0.8)

        # update count now and once per second going forward..
        self._tickingNode = None
        self._smoothTicketCount = None
        self._ticketCount = 0
        self._update()
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._smoothIncreaseSpeed = 1.0
        
    def __del__(self):
        if self._tickingNode is not None:
            self._tickingNode.delete()
            self._tickingNode = None
        
    def _smoothUpdate(self):
        if not self._ticketCountText.exists():
            self._smoothUpdateTimer = None
            return
        
        finished = False
        
        # if we're going down, do it immediately
        if int(self._smoothTicketCount) >= self._ticketCount:
            self._smoothTicketCount = float(self._ticketCount)
            finished = True
        else:
            # we're going up; start a sound if need be
            self._smoothTicketCount = min(self._smoothTicketCount + 1.0 * self._smoothIncreaseSpeed,self._ticketCount)
            if int(self._smoothTicketCount) >= self._ticketCount:
                finished = True
                self._smoothTicketCount = float(self._ticketCount)
            elif self._tickingNode is None:
                with bs.Context('UI'):
                    self._tickingNode = bs.newNode('sound',attrs={'sound':bs.getSound('scoreIncrease'),'positional':False})
            
        bs.textWidget(edit=self._ticketCountText,text=str(int(self._smoothTicketCount)))

        # if we've reached the target, kill the timer/sound/etc
        if finished:
            self._smoothUpdateTimer = None
            if self._tickingNode is not None:
                self._tickingNode.delete()
                self._tickingNode = None
                bs.playSound(bs.getSound('cashRegister2'))
        
    def _update(self):
        import datetime
        
        # if we somehow get signed out, just die..
        if bsInternal._getAccountState() != 'SIGNED_IN':
            self._back()
            return
        
        self._ticketCount = bsInternal._getAccountTicketCount()

        # update our incentivized ad button depending on whether ads are available
        if self._adButton is not None:
            nextRewardAdTime = bsInternal._getAccountMiscReadVal2('nextRewardAdTime', None)
            if nextRewardAdTime is not None:
                nextRewardAdTime = datetime.datetime.utcfromtimestamp(nextRewardAdTime)
            now = datetime.datetime.utcnow()
                
            if bsInternal._haveIncentivizedAd() and (nextRewardAdTime is None or nextRewardAdTime <= now):
                bs.buttonWidget(edit=self._adButton, color=(0.65,0.5,0.7))
                bs.textWidget(edit=self._adLabel, color=(0.7,0.9,0.7,1.0))
                bs.textWidget(edit=self._adFreeText, color=(1,1,0,1))
                bs.imageWidget(edit=self._adImage, opacity=0.6)
                bs.textWidget(edit=self._adTimeText, text='')
            else:
                bs.buttonWidget(edit=self._adButton,color=(0.5,0.5,0.5))
                bs.textWidget(edit=self._adLabel,color=(0.7,0.9,0.7,0.2))
                bs.textWidget(edit=self._adFreeText,color=(1,1,0,0.2))
                bs.imageWidget(edit=self._adImage,opacity=0.6*0.25)
                if nextRewardAdTime is not None and nextRewardAdTime > now:
                    s = bsUtils.getTimeString((nextRewardAdTime-now).total_seconds()*1000.0, centi=False)
                else:
                    s = ''
                bs.textWidget(edit=self._adTimeText, text=s)
                
        # if this is our first update, assign immediately; otherwise kick off a smooth transition if the value has changed
        if self._smoothTicketCount is None:
            self._smoothTicketCount = float(self._ticketCount)
            self._smoothUpdate() # will set the text widget
            
        elif self._ticketCount != self._smoothTicketCount and self._smoothUpdateTimer is None:
            self._smoothUpdateTimer = bs.Timer(50,bs.WeakCall(self._smoothUpdate),repeat=True,timeType='real')
            diff = abs(float(self._ticketCount)-self._smoothTicketCount)
            self._smoothIncreaseSpeed = diff/100.0 if diff >= 5000 else diff/50.0 if diff >= 1500 else diff/30.0 if diff >= 500 else diff/15.0
            
    def _disabledPress(self):

        # if we're on a platform without purchases, inform the user they
        # can link their accounts and buy stuff elsewhere
        env = bs.getEnvironment()
        if (env['testBuild'] or (env['platform'] == 'android' and env['subplatform'] in ['oculus','cardboard'])) and bsInternal._getAccountMiscReadVal('allowAccountLinking2',False):
            bs.screenMessage(self._R.unavailableLinkAccountText,color=(1,0.5,0))
        else:
            bs.screenMessage(self._R.unavailableText,color=(1,0.5,0))
        bs.playSound(bs.getSound('error'))

    def _purchase(self,item):
        if item == 'appInvite':
            if bsInternal._getAccountState() != 'SIGNED_IN':
                showSignInPrompt()
                return
            doAppInvitesPress()
            return
        # here we ping the server to ask if it's valid for us to purchase this..
        # (better to fail now than after we've paid locally)
        env = bs.getEnvironment()
        bsUtils.serverGet('bsAccountPurchaseCheck',{'item':item,'platform':env['platform'],'subplatform':env['subplatform'],'version':env['version'],'buildNumber':env['buildNumber']},
                          callback=bs.WeakCall(self._purchaseCheckResult,item))
        
    def _purchaseCheckResult(self,item,result):
        if result is None:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('internal.unavailableNoConnectionText'),color=(1,0,0))
        else:
            if result['allow']: self._doPurchase(item)
            else:
                if result['reason'] == 'versionTooOld':
                    bs.playSound(bs.getSound('error'))
                    bs.screenMessage(bs.getResource('getTicketsWindow.versionTooOldText'),color=(1,0,0))
                else:
                    bs.playSound(bs.getSound('error'))
                    bs.screenMessage(bs.getResource('getTicketsWindow.unavailableText'),color=(1,0,0))

    # actually start the purchase locally..
    def _doPurchase(self,item):
        if item == 'ad':
            import datetime
            # if ads are disabled until some time, error..
            nextRewardAdTime = bsInternal._getAccountMiscReadVal2('nextRewardAdTime', None)
            if nextRewardAdTime is not None:
                nextRewardAdTime = datetime.datetime.utcfromtimestamp(nextRewardAdTime)
            now = datetime.datetime.utcnow()
            if nextRewardAdTime is not None and nextRewardAdTime > now:
                bs.playSound(bs.getSound('error'))
                bs.screenMessage(bs.getResource('getTicketsWindow.unavailableTemporarilyText'),color=(1,0,0))
            elif self._enableAdButton:
                bsUtils._showAd('tickets')
        else:
            bsInternal._purchase(item)
        
    def _back(self):
        if self._transitioningOut: return
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if not self._modal:
            window = StoreWindow(transition='inLeft',modal=self._fromModalStore,backLocation=self._storeBackLocation).getRootWidget()
            if not self._fromModalStore:
                uiGlobals['mainMenuWindow'] = window
        self._transitioningOut = True

def _createTabButtons(parentWidget,tabs,pos,size,onSelectCall=None,returnExtraInfo=False):
    
    tabPosV = pos[1]
    tabButtons = {}
    tabButtonsIndexed = []
    tabButtonWidth = float(size[0])/len(tabs)
    
    # add a bit more visual spacing as our buttons get narrower
    tabSpacing = (250.0-tabButtonWidth)*0.06

    positions = []
    sizes = []
    
    h = pos[0]
    for i,tab in enumerate(tabs):
        def _tickAndCall(call):
            bs.playSound(bs.getSound('click01'))
            onSelectCall(call)

        pos = (h+tabSpacing*0.5,tabPosV)
        size = (tabButtonWidth-tabSpacing,50.0)
        positions.append(pos)
        sizes.append(size)
        b = bs.buttonWidget(parent=parentWidget,position=pos,autoSelect=True,
                            buttonType='tab',size=size,label=tab[1],enableSound=False,
                            onActivateCall=bs.Call(_tickAndCall,tab[0]))
        h += tabButtonWidth
        tabButtons[tab[0]] = b
        tabButtonsIndexed.append(b)
    if returnExtraInfo: return {'buttons':tabButtons,'buttonsIndexed':tabButtonsIndexed,'positions':positions,'sizes':sizes}
    else: return tabButtons

def _updateTabButtonColors(tabs,selectedTab):
    for tId,tButton in tabs.items():
        if tId == selectedTab: bs.buttonWidget(edit=tButton,color=(0.5,0.4,0.93),textColor=(0.85,0.75,0.95)) # lit
        else: bs.buttonWidget(edit=tButton,color=(0.52,0.48,0.63),textColor=(0.65,0.6,0.7)) # unlit


class TestWindow(Window):
    def __init__(self,transition='inRight'):
        self._width = 500
        self._height = 350
        
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,
                                              scale=1.8 if gSmallUI else 1.6 if gMedUI else 1.4)

        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(30,self._height-54),size=(120,50),scale=1.1,
                                                            label=bs.getResource('backText'),buttonType='back', onActivateCall=self._back)

        scroll1 = bs.scrollWidget(parent=self._rootWidget,size=(440,270),position=(40,30),highlight=False)
        bs.containerWidget(edit=scroll1,claimsLeftRight=True)
        sc = bs.containerWidget(parent=scroll1,size=(400,800),background=False)
        bs.widget(edit=sc,autoSelect=True)

        scroll2 = bs.hScrollWidget(parent=sc,size=(430,200),position=(-5,550),highlight=False,borderOpacity=0.3)
        bs.widget(edit=scroll2,showBufferTop=40,showBufferBottom=40,autoSelect=True)
        bs.containerWidget(edit=scroll2,claimsLeftRight=True)
        sc2 = bs.containerWidget(parent=scroll2,size=(1200,200),background=False)

        b1 = bs.buttonWidget(parent=sc,position=(20,760),autoSelect=True)
        b1 = bs.buttonWidget(parent=sc,position=(20,480),autoSelect=True)
        b2 = bs.buttonWidget(parent=sc,position=(30,380),autoSelect=True)
        b3 = bs.buttonWidget(parent=sc,position=(40,280),autoSelect=True)

        x = 10
        dx = 160
        for i in range(6):
            b = bs.buttonWidget(parent=sc2,position=(x,25),autoSelect=True,size=(150,150),
                                buttonType='square',onActivateCall=bs.Call(bs.screenMessage,"CLICK!"))
            bs.widget(edit=b,showBufferLeft=50,showBufferRight=50,downWidget=b1,upWidget=self._backButton)
            x += dx
        
    def _back(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()
        
        
class WatchWindow(Window):

    def __init__(self,transition='inRight',originWidget=None):

        bsInternal._setAnalyticsScreen('Watch Window')
        
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        global gMainWindow
        gMainWindow = "Watch"
        
        self._R = bs.getResource('watchWindow')
        
        self._width = 1040
        self._height = 578 if gSmallUI else 670 if gMedUI else 800
        self._currentTab = None
        extraTop = 20 if gSmallUI else 0

        self._rootWidget = bs.containerWidget(size=(self._width,self._height+extraTop),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=1.3 if gSmallUI else 0.97 if gMedUI else 0.8,
                                              stackOffset=(0,-10) if gSmallUI else (0,15) if gMedUI else (0,0))
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,autoSelect=True,position=(70,self._height-74),
                                                            size=(140,60),scale=1.1,label=bs.getResource('backText'),
                                                            buttonType='back', onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-38),size=(0,0),
                          color=gTitleColor,scale=1.5,hAlign="center",vAlign="center",
                          text=self._R.titleText,
                          maxWidth=400)

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(155,self._height - 40))
        
        tabsDef = [['myReplays',self._R.myReplaysText]]
                   #['sharedReplays',self._R.sharedReplaysText]]

        scrollBufferH = 130
        tabBufferH = 750
        
        self._tabButtons = _createTabButtons(self._rootWidget,tabsDef,pos=(tabBufferH*0.5,self._height - 130),
                                             size=(self._width-tabBufferH,50),onSelectCall=self._setTab)

        self._scrollWidth = self._width-scrollBufferH
        self._scrollHeight = self._height-180

        # not actually using a scroll widget anymore; just an image
        scrollLeft = (self._width-self._scrollWidth)*0.5
        scrollBottom = self._height-self._scrollHeight-79-48
        bufferH = 10
        bufferV = 4
        bs.imageWidget(parent=self._rootWidget,position=(scrollLeft-bufferH,scrollBottom-bufferV),size=(self._scrollWidth+2*bufferH,self._scrollHeight+2*bufferV),
                       texture=bs.getTexture('scrollWidget'),modelTransparent=bs.getModel('softEdgeOutside'))
        self._tabContainer = None

        self._restoreState()
        
    def _setTab(self,tab):

        if self._currentTab == tab: return
        self._currentTab = tab

        # we wanna preserve our current tab between runs
        bs.getConfig()['Watch Tab'] = tab
        bs.writeConfig()
        
        # update tab colors based on which is selected
        _updateTabButtonColors(self._tabButtons,tab)
        
        if self._tabContainer is not None and self._tabContainer.exists():
            self._tabContainer.delete()
        scrollLeft = (self._width-self._scrollWidth)*0.5
        scrollBottom = self._height-self._scrollHeight-79-48

        # a place where tabs can store data to get cleared when switching to a different tab
        self._tabData = {}
        
        def _simpleMessage(message):
            msgScale = 1.1
            cWidth = self._scrollWidth
            cHeight = min(self._scrollHeight,bs.getStringHeight(message)*msgScale+100)
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectable=False)
            bs.widget(edit=c,upWidget=self._tabButtons[tab])
            
            t = bs.textWidget(parent=c,position=(cWidth*0.5,cHeight*0.5),color=(0.6,1.0,0.6),scale=msgScale,
                              size=(0,0),maxWidth=cWidth*0.9,maxHeight=cHeight*0.9,
                              hAlign='center',vAlign='center',
                              text=message)
        
        if tab == 'myReplays':
            cWidth = self._scrollWidth
            cHeight = self._scrollHeight-20
            subScrollHeight = cHeight - 63
            self._myReplaysScrollWidth = subScrollWidth = (680 if gSmallUI else 640)

            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)

            v = cHeight - 30
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=0.7,
                              size=(0,0),
                              maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=bs.getResource('replayRenameWarningText').replace('${REPLAY}',bs.getResource('replayNameDefaultText')))

            bWidth = 140 if gSmallUI else 178
            bHeight = 107 if gSmallUI else 142 if gMedUI else 190
            bSpaceExtra = 0 if gSmallUI else -2 if gMedUI else -5
            
            bColor = (0.6,0.53,0.63)
            bTextColor = (0.75,0.7,0.8)
            bv = cHeight-(48 if gSmallUI else 45 if gMedUI else 40)-bHeight
            bh = 40 if gSmallUI else 40
            sh = 190 if gSmallUI else 225
            ts = 1.0 if gSmallUI else 1.2
            self._myReplaysWatchReplayButton = b1 = bs.buttonWidget(parent=c,size=(bWidth,bHeight),position=(bh,bv),
                                                                    buttonType='square',color=bColor,textColor=bTextColor,
                                                                    onActivateCall=self._onMyReplayPlayPress,textScale=ts,
                                                                    label=self._R.watchReplayButtonText,autoSelect=True)
            bs.widget(edit=b1,upWidget=self._tabButtons[tab])
            bv -= bHeight+bSpaceExtra
            b2 = bs.buttonWidget(parent=c,size=(bWidth,bHeight),position=(bh,bv),
                            buttonType='square',color=bColor,textColor=bTextColor,
                                 onActivateCall=self._onMyReplayRenamePress,textScale=ts,
                            label=self._R.renameReplayButtonText,autoSelect=True)
            bv -= bHeight+bSpaceExtra
            b3 = bs.buttonWidget(parent=c,size=(bWidth,bHeight),position=(bh,bv),
                            buttonType='square',color=bColor,textColor=bTextColor,
                                 onActivateCall=self._onMyReplayDeletePress,textScale=ts,
                            label=self._R.deleteReplayButtonText,autoSelect=True)
            
            v -= subScrollHeight+23
            self._scrollWidget = sw = bs.scrollWidget(parent=c,position=(sh,v),size=(subScrollWidth,subScrollHeight))
            bs.containerWidget(edit=c,selectedChild=sw)
            self._columnWidget = bs.columnWidget(parent=sw,leftBorder=10)
            
            bs.widget(edit=sw,autoSelect=True,leftWidget=b1,upWidget=self._tabButtons[tab])
            bs.widget(edit=self._tabButtons[tab],downWidget=sw)

            self._myReplaySelected = None
            self._refreshMyReplays()
        elif tab == 'sharedReplays':
            _simpleMessage(('(COMING SOON)\n'
                            'This section will include replays that your friends\n'
                            'have shared with you or possibly public replays\n'
                            'from recent online tournaments, etc.'))
        elif tab == 'bestMoments':
            _simpleMessage(('(COMING SOON)\n'
                            'This section will highlight short snippets of replays\n'
                            'that people have shared, each only a few seconds long;\n'
                            'awesome moves, random moments of hilarity, etc.'))

    def _noReplaySelectedError(self):
        bs.screenMessage(self._R.noReplaySelectedErrorText,color=(1,0,0))
        bs.playSound(bs.getSound('error'))

    def _onMyReplayPlayPress(self):
        if self._myReplaySelected is None:
            self._noReplaySelectedError()
            return

        bsInternal._incrementAnalyticsCount('Replay watch')
        def doIt():
            try:
                bsInternal._fadeScreen(True)
                bsInternal._newReplaySession(bsInternal._getReplaysDir()+'/'+self._myReplaySelected)
            except Exception:
                import bsMainMenu
                bs.printException("exception running replay session")
                # drop back into a fresh main menu session in case we half-launched or something..
                bsInternal._newHostSession(bsMainMenu.MainMenuSession)
        bsInternal._fadeScreen(False,time=250,endCall=bs.Call(bs.pushCall,doIt))
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')

    def _onMyReplayRenamePress(self):
        if self._myReplaySelected is None:
            self._noReplaySelectedError()
            return
        cWidth = 600
        cHeight = 250
        self._myReplaysRenameWindow = c = bs.containerWidget(scale=1.8 if gSmallUI else 1.55 if gMedUI else 1.0,
                                                             size=(cWidth,cHeight),transition='inScale')
        dName = self._getReplayDisplayName(self._myReplaySelected)
        bs.textWidget(parent=c,size=(0,0),hAlign='center',vAlign='center',text=self._R.renameReplayText.replace('${REPLAY}',dName),
                      maxWidth=cWidth*0.8,
                      position=(cWidth*0.5,cHeight-60))
        self._myReplayRenameText = t = bs.textWidget(parent=c,size=(cWidth*0.8,40),hAlign='left',vAlign='center',text=dName,
                                                     editable=True,description=self._R.replayNameText,position=(cWidth*0.1,cHeight-140),autoSelect=True,maxWidth=cWidth*0.7,maxChars=200)
        cb = bs.buttonWidget(parent=c,label=bs.getResource('cancelText'),
                             onActivateCall=bs.Call(bs.containerWidget,edit=c,transition='outScale'),size=(180,60),position=(30,30),autoSelect=True)
        okb = bs.buttonWidget(parent=c,label=self._R.renameText,size=(180,60),position=(cWidth-230,30),
                              onActivateCall=bs.Call(self._renameMyReplay,self._myReplaySelected),autoSelect=True)
        bs.widget(edit=cb,rightWidget=okb)
        bs.widget(edit=okb,leftWidget=cb)
        bs.textWidget(edit=t,onReturnPressCall=okb.activate)
        bs.containerWidget(edit=c,cancelButton=cb,startButton=okb)

    def _renameMyReplay(self,replay):
        try:
            if not self._myReplayRenameText.exists():
                return
            newNameRaw = bs.textWidget(query=self._myReplayRenameText)
            newName = newNameRaw+'.brp'
            # ignore attempts to change it to what it already is (or what it looks like to the user)
            if replay != newName and self._getReplayDisplayName(replay) != newNameRaw:
                oldNameFull = (bsInternal._getReplaysDir()+'/'+replay).encode('utf-8')
                newNameFull = (bsInternal._getReplaysDir()+'/'+newName).encode('utf-8')
                if os.path.exists(newNameFull):
                    bs.playSound(bs.getSound('error'))
                    bs.screenMessage(self._R.replayRenameErrorAlreadyExistsText,color=(1,0,0))
                elif any(char in newNameRaw for char in ['/','\\',':']):
                    bs.playSound(bs.getSound('error'))
                    bs.screenMessage(self._R.replayRenameErrorInvalidName,color=(1,0,0))
                else:
                    bsInternal._incrementAnalyticsCount('Replay rename')
                    os.rename(oldNameFull,newNameFull)
                    self._refreshMyReplays()
                    bs.playSound(bs.getSound('gunCocking'))
        except Exception:
            bs.printException("error renaming replay '"+replay+"' to '"+newName+"'")
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.replayRenameErrorText,color=(1,0,0))
            
        bs.containerWidget(edit=self._myReplaysRenameWindow,transition='outScale')
            
        
    def _onMyReplayDeletePress(self):
        if self._myReplaySelected is None:
            self._noReplaySelectedError()
            return
        ConfirmWindow(self._R.deleteConfirmText.replace('${REPLAY}',self._getReplayDisplayName(self._myReplaySelected)),
                      bs.Call(self._deleteReplay,self._myReplaySelected),450,150)

    def _getReplayDisplayName(self,replay):
        if replay.endswith('.brp'):
            replay = replay[:-4]
        if replay == '__lastReplay': return bs.getResource('replayNameDefaultText')
        return replay
    
    def _deleteReplay(self,replay):
        try:
            bsInternal._incrementAnalyticsCount('Replay delete')
            os.remove((bsInternal._getReplaysDir()+'/'+replay).encode('utf-8'))
            self._refreshMyReplays()
            bs.playSound(bs.getSound('shieldDown'))
            if replay == self._myReplaySelected: self._myReplaySelected = None
        except Exception:
            bs.printException("exception deleting replay '"+replay+"'")
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(self._R.replayDeleteErrorText,color=(1,0,0))
        
    def _onMyReplaySelect(self,replay):
        self._myReplaySelected = bs.uni(replay)

    def _refreshMyReplays(self):
        for c in self._columnWidget.getChildren(): c.delete()
        tScale = 1.6
        try:
            names = os.listdir(bsInternal._getReplaysDir())
            names = [bs.uni(n) for n in names if n.endswith('.brp')] # ignore random other files in there..
            names.sort(key=lambda x:x.lower())
        except Exception:
            bs.printException("error listing replays dir")
            names = []
        
        for i,name in enumerate(names):
            t = bs.textWidget(parent=self._columnWidget,size=(self._myReplaysScrollWidth/tScale,30),selectable=True,
                              color=(1.0,1,0.4) if name == '__lastReplay.brp' else (1,1,1),alwaysHighlight=True,
                              onSelectCall=bs.Call(self._onMyReplaySelect,name),
                              onActivateCall=self._myReplaysWatchReplayButton.activate,
                              text=self._getReplayDisplayName(name),hAlign='left',vAlign='center',cornerScale=tScale,
                              maxWidth=(self._myReplaysScrollWidth/tScale)*0.93)
            if i == 0:
                bs.widget(edit=t,upWidget=self._tabButtons['myReplays'])
    
    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._backButton: selName = 'Back'
            elif sel in self._tabButtons.values():
                selName = 'Tab:'+self._tabButtons.keys()[self._tabButtons.values().index(sel)]
            elif sel == self._tabContainer: selName = 'TabContainer'
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = {'selName':selName,'tab':self._currentTab}
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]['selName']
            except Exception: selName = None
            try: currentTab = bs.getConfig()['Watch Tab']
            except Exception: currentTab = None
            if currentTab is None or currentTab not in self._tabButtons: currentTab = 'myReplays'
            self._setTab(currentTab)
            if selName == 'Back': sel = self._backButton
            elif selName == 'TabContainer': sel = self._tabContainer
            elif type(selName) is str and selName.startswith('Tab:'): sel = self._tabButtons[selName.split(':')[-1]]
            else:
                if self._tabContainer is not None: sel = self._tabContainer
                else: sel = self._tabButtons[currentTab]
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)
            
    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()

gShowedNetPlayWarning = False


class GatherWindow(Window):

    def __del__(self):
        bsInternal._setPartyIconAlwaysVisible(False)

    def __init__(self,transition='inRight',originWidget=None):

        bsInternal._setAnalyticsScreen('Gather Window')
        
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        global gMainWindow
        gMainWindow = "Gather"
        
        bsInternal._setPartyIconAlwaysVisible(True)
        
        self._width = 1040
        self._height = 582 if gSmallUI else 680 if gMedUI else 800
        self._currentTab = None
        extraTop = 20 if gSmallUI else 0

        self._R = bs.getResource('gatherWindow')

        self._rootWidget = bs.containerWidget(size=(self._width,self._height+extraTop),transition=transition,
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=1.3 if gSmallUI else 0.97 if gMedUI else 0.8,
                                              stackOffset=(0,-11) if gSmallUI else (0,0) if gMedUI else (0,0))
        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(70,self._height-74),size=(140,60),scale=1.1,
                                                            autoSelect=True,label=bs.getResource('backText'),buttonType='back', onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)
        
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-42),size=(0,0),
                          color=gTitleColor,scale=1.5,hAlign="center",vAlign="center",
                          text=self._R.titleText,
                          maxWidth=550)

        if gDoAndroidNav:
            bs.buttonWidget(edit=b,buttonType='backSmall',position=(70,self._height-78),size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(155,self._height - 44))

        
        platform = bs.getEnvironment()['platform']
        subplatform = bs.getEnvironment()['subplatform']
        
        tabsDef = [['about',self._R.aboutText]]
        if False: tabsDef.append(['internet',self._R.internetText])
        if platform == 'android' and subplatform == 'google':
            tabsDef.append(['googlePlus',self._R.googlePlayText])
        tabsDef.append(['localNetwork',self._R.localNetworkText])
        
        if platform == 'android' and subplatform in ['','google'] and not bs.getEnvironment()['onTV']:
            tabsDef.append(['wifiDirect',self._R.wifiDirectText])
            
        tabsDef.append(['manual',self._R.manualText])

        scrollBufferH = 130
        tabBufferH = 250
        
        self._tabButtons = _createTabButtons(self._rootWidget,tabsDef,pos=(tabBufferH*0.5,self._height - 130),
                                             size=(self._width-tabBufferH,50),onSelectCall=self._setTab)

        self._scrollWidth = self._width-scrollBufferH
        self._scrollHeight = self._height-180

        # not actually using a scroll widget anymore; just an image
        scrollLeft = (self._width-self._scrollWidth)*0.5
        scrollBottom = self._height-self._scrollHeight-79-48
        bufferH = 10
        bufferV = 4
        bs.imageWidget(parent=self._rootWidget,position=(scrollLeft-bufferH,scrollBottom-bufferV),size=(self._scrollWidth+2*bufferH,self._scrollHeight+2*bufferV),
                       texture=bs.getTexture('scrollWidget'),modelTransparent=bs.getModel('softEdgeOutside'))
        self._tabContainer = None
        self._restoreState()

    def _showWarning(self):
        global gShowedNetPlayWarning
        if not gShowedNetPlayWarning:
            gShowedNetPlayWarning = True
            env = bs.getEnvironment()
            if not env['debugBuild']:
                ConfirmWindow(self._R.inDevelopmentWarningText,
                              color=(0.7,1.0,0.7),width=500,height=205,cancelButton=False)

    def _onGooglePlayShowInvitesPress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN'  or bsInternal._getAccountType() != 'Google Play':
            showSignInPrompt('Google Play')
        else:
            bsInternal._showInvitesUI()
    
    def _onGooglePlayInvitePress(self):

        if bsInternal._getAccountState() != 'SIGNED_IN' or bsInternal._getAccountType() != 'Google Play':
            showSignInPrompt('Google Play')
        else:
            # if there's google play people connected to us, inform the user that they will get disconnected..
            # otherwise just go ahead..
            googlePlayerCount = bsInternal._getGooglePlayPartyClientCount()
            if googlePlayerCount > 0:
                ConfirmWindow(self._R.googlePlayReInviteText.replace('${COUNT}',str(googlePlayerCount)),bs.Call(bs.realTimer,200,bsInternal._invitePlayers),
                              width=500,height=150,okText=self._R.googlePlayInviteText)
            else:
                bs.realTimer(100,bsInternal._invitePlayers)

    def _inviteToTryPress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        doAppInvitesPress()
        
    def _setTab(self,tab):

        if self._currentTab == tab: return
        self._currentTab = tab

        # we wanna preserve our current tab between runs
        bs.getConfig()['Gather Tab'] = tab
        bs.writeConfig()
        
        # update tab colors based on which is selected
        _updateTabButtonColors(self._tabButtons,tab)
        
        # (re)create scroll widget
        if self._tabContainer is not None and self._tabContainer.exists():
            self._tabContainer.delete()
        scrollLeft = (self._width-self._scrollWidth)*0.5
        scrollBottom = self._height-self._scrollHeight-79-48

        # a place where tabs can store data to get cleared when switching to a different tab
        self._tabData = {}
        
        # so we can still select root level widgets with direction buttons
        def _simpleMessage(tab,message,includeInvite=False):
            msgScale = 1.1
            cWidth = self._scrollWidth
            cHeight = min(self._scrollHeight,bs.getStringHeight(message)*msgScale+100)
            tryTickets = bsInternal._getAccountMiscReadVal('friendTryTickets',None)
            if tryTickets is None: includeInvite = False
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectable=True if includeInvite else False)
            bs.widget(edit=c,upWidget=self._tabButtons[tab])
            
            t = bs.textWidget(parent=c,position=(cWidth*0.5,cHeight*(0.58 if includeInvite else 0.5)),
                              color=(0.6,1.0,0.6),scale=msgScale,
                              size=(0,0),maxWidth=cWidth*0.9,maxHeight=cHeight*(0.7 if includeInvite else 0.9),
                              hAlign='center',vAlign='center',
                              text=message)
            if includeInvite:
                t = bs.textWidget(parent=c,position=(cWidth*0.57,35),
                                  color=(0,1,0),scale=0.6,
                                  size=(0,0),maxWidth=cWidth*0.5,
                                  hAlign='right',vAlign='center',
                                  flatness=1.0,
                                  text=self._R.inviteAFriendText.replace('${COUNT}',str(tryTickets)))
                bs.buttonWidget(parent=c,position=(cWidth*0.59,10),
                                size=(230,50),
                                color=(0.54,0.42,0.56),
                                textColor=(0,1,0),
                                label=bs.getResource('gatherWindow.inviteFriendsText',fallback='gatherWindow.getFriendInviteCodeText'),
                                autoSelect=True,
                                onActivateCall=bs.WeakCall(self._inviteToTryPress),
                                upWidget=self._tabButtons[tab])


        if tab == 'about':
            msg = bs.uni(self._R.aboutDescriptionText)
            msg = msg.replace('${PARTY}',bs.getSpecialChar('partyIcon'))
            msg = msg.replace('${BUTTON}',bs.getSpecialChar('topButton'))

            # let's not talk about sharing in vr-mode; its tricky to fit more than
            # one head in a VR-headset ;-)
            if not bs.getEnvironment()['vrMode']:
                msg += '\n\n'+bs.uni(self._R.aboutDescriptionLocalMultiplayerExtraText)
                
            _simpleMessage(tab,msg,includeInvite=True)
            
        elif tab == 'googlePlus':
            cWidth = self._scrollWidth
            cHeight = 380
            bWidth = 250
            bWidth2 = 230
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)
            imgSize = 100
            v = cHeight-30
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=1.3,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.googlePlayDescriptionText)
            v -= 35
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=0.7,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.worksWithGooglePlayDevicesText)
            v -= 125
            b = bs.buttonWidget(parent=c,label='',position=(cWidth*0.5-bWidth*0.5,v-bWidth*0.5),size=(bWidth,bWidth*0.9),
                                #buttonType='square',onActivateCall=bs.Call(bs.realTimer,100,bsInternal._invitePlayers),
                                buttonType='square',onActivateCall=self._onGooglePlayInvitePress,
                                autoSelect=True,upWidget=self._tabButtons[tab])
            bs.imageWidget(parent=c,position=(cWidth*0.5-imgSize*0.5,v-35),size=(imgSize,imgSize),
                           drawController=b,texture=bs.getTexture('googlePlayGamesIcon'),color=(0,1,0))
            bs.textWidget(parent=c,text=self._R.googlePlayInviteText,maxWidth=bWidth*0.8,drawController=b,color=(0,1,0),flatness=1.0,
                          position=(cWidth*0.5,v-60),scale=1.6,size=(0,0),hAlign='center',vAlign='center')
            v -= 180
            bs.buttonWidget(parent=c,label=self._R.googlePlaySeeInvitesText,
                            color=(0.5,0.5,0.6),textColor=(0.75,0.7,0.8),
                            autoSelect=True,
                            position=(cWidth*0.5-bWidth2*0.5,v),
                            size=(bWidth2,60),
                            onActivateCall=bs.Call(bs.realTimer,100,self._onGooglePlayShowInvitesPress))

        elif tab == 'internet':
            cWidth = self._scrollWidth
            cHeight = self._scrollHeight-20
            subScrollHeight = cHeight - 85
            subScrollWidth = 650
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)
            v = cHeight - 30
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v-3),color=(0.6,1.0,0.6),scale=1.3,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.publicPartyDescriptionText)
            v -= 15
            v -= subScrollHeight+23
            sw = bs.scrollWidget(parent=c,position=((self._scrollWidth-subScrollWidth)*0.5,v),size=(subScrollWidth,subScrollHeight))

            self._tabData = {}
            
            bs.widget(edit=sw,autoSelect=True,upWidget=self._tabButtons[tab])
            
        elif tab == 'localNetwork':
            cWidth = self._scrollWidth
            cHeight = self._scrollHeight-20
            subScrollHeight = cHeight - 85
            subScrollWidth = 650

            class NetScanner(object):
                def __init__(self,scrollWidget,tabButton,width):
                    self._scrollWidget = scrollWidget
                    self._tabButton = tabButton
                    self._columnWidget = bs.columnWidget(parent=self._scrollWidget,leftBorder=10)
                    bs.widget(edit=self._columnWidget,upWidget=tabButton)
                    self._width = width
                    self._lastSelectedHost = None

                    self._updateTimer = bs.Timer(1000,bs.WeakCall(self.update),timeType='real',repeat=True)
                    # go ahead and run a few *almost* immediately so we dont have to wait a second
                    self.update()
                    bs.realTimer(250,bs.WeakCall(self.update))
                    
                def __del__(self):
                    bsInternal._endHostScanning()

                def _onSelect(self,host):
                    self._lastSelectedHost = host

                def _onActivate(self,host):
                    bsInternal._connectToParty(host['address'])
                    #bs.screenMessage("WOULD CONNECT TO '"+host['address']+"'")
                        
                def update(self):
                    tScale = 1.6
                    for c in self._columnWidget.getChildren(): c.delete()
                    lastSelectedHost = self._lastSelectedHost # grab this now this since adding widgets will change it
                    hosts = bsInternal._hostScanCycle()
                    for i,host in enumerate(hosts):
                        t = bs.textWidget(parent=self._columnWidget,size=(self._width/tScale,30),selectable=True,
                                          #color=(0,1,0),
                                          color=(1,1,1),
                                          onSelectCall=bs.Call(self._onSelect,host),
                                          onActivateCall=bs.Call(self._onActivate,host),clickActivate=True,
                                          text=host['displayString'],hAlign='left',vAlign='center',cornerScale=tScale,maxWidth=(self._width/tScale)*0.93)
                                          #text=host['name']+"_"+host['pubID'],hAlign='left',vAlign='center',cornerScale=tScale,maxWidth=(self._width/tScale)*0.93)
                        if host == lastSelectedHost:
                            bs.containerWidget(edit=self._columnWidget,selectedChild=t,visibleChild=t)
                        if i == 0: bs.widget(edit=t,upWidget=self._tabButton)
            
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)
            v = cHeight - 30
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v-3),color=(0.6,1.0,0.6),scale=1.3,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.localNetworkDescriptionText)
            v -= 15
            # t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=0.7,
            #                   size=(0,0),maxWidth=cWidth*0.9,
            #                   hAlign='center',vAlign='center',
            #                   text=self._R.worksBetweenAllPlatformsText)
            v -= subScrollHeight+23
            sw = bs.scrollWidget(parent=c,position=((self._scrollWidth-subScrollWidth)*0.5,v),size=(subScrollWidth,subScrollHeight))

            self._tabData = NetScanner(sw,self._tabButtons[tab],width=subScrollWidth)
            
            
            bs.widget(edit=sw,autoSelect=True,upWidget=self._tabButtons[tab])
            # t = bs.textWidget(parent=c,position=(cWidth*0.5,v+subScrollHeight*0.5),color=(1,1,1),scale=0.9,
            #                   size=(0,0),maxWidth=cWidth*0.9,
            #                   hAlign='center',vAlign='center',
            #                   text='(not wired up yet)')

            # _simpleMessage(('TODO: add local network UI here'))

        elif tab == 'bluetooth':
            cWidth = self._scrollWidth
            cHeight = 380
            subScrollHeight = cHeight - 150
            subScrollWidth = 650

            bWidth = 250
            bWidth2 = 230
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)
            imgSize = 100
            v = cHeight-30
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=1.3,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.bluetoothDescriptionText)
            v -= 35
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=0.7,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.bluetoothAndroidSupportText)

            v -= 55
            b = bs.buttonWidget(parent=c,position=(cWidth*0.5-subScrollWidth*0.5+10,v-75),size=(300,70),autoSelect=True,
                                onActivateCall=bsInternal._bluetoothAdvertise,
                                label=self._R.bluetoothHostText)
            bs.widget(edit=b,upWidget=self._tabButtons[tab])
            b = bs.buttonWidget(parent=c,position=(cWidth*0.5-subScrollWidth*0.5+330,v-75),size=(300,70),autoSelect=True,
                                onActivateCall=bs.Call(bs.screenMessage,'FIXME: not wired up yet'),
                                label=self._R.bluetoothJoinText)
            bs.widget(edit=b,upWidget=self._tabButtons[tab])
            bs.widget(edit=self._tabButtons[tab],downWidget=b)
            
        elif tab == 'wifiDirect':
            cWidth = self._scrollWidth
            cHeight = self._scrollHeight-20
            subScrollHeight = cHeight - 100
            subScrollWidth = 650
            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)
            v = cHeight - 80

            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=1.0,
                              size=(0,0),maxWidth=cWidth*0.95,maxHeight=140,
                              hAlign='center',vAlign='center',
                              text=self._R.wifiDirectDescriptionTopText)
            v -= 140
            b = bs.buttonWidget(parent=c,position=(cWidth*0.5-175,v),size=(350,65),label=self._R.wifiDirectOpenWiFiSettingsText,
                            autoSelect=True,onActivateCall=bsInternal._androidShowWifiSettings)
            v -= 82
            
            bs.widget(edit=b,upWidget=self._tabButtons[tab])

            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=0.9,
                              size=(0,0),maxWidth=cWidth*0.95,maxHeight=150,
                              hAlign='center',vAlign='center',
                              text=self._R.wifiDirectDescriptionBottomText.replace('${APP_NAME}',bs.getResource('titleText')))
            

        elif tab == 'manual':
            cWidth = self._scrollWidth
            cHeight = 380

            try: lastAddr = bs.getConfig()['Last Manual Party Connect Address']
            except Exception: lastAddr = ''

            self._tabContainer = c = bs.containerWidget(parent=self._rootWidget,
                                                        position=(scrollLeft,scrollBottom+(self._scrollHeight-cHeight)*0.5),
                                                        size=(cWidth,cHeight),background=False,selectionLoopToParent=True)
            v = cHeight-30
            t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=1.3,
                              size=(0,0),maxWidth=cWidth*0.9,
                              hAlign='center',vAlign='center',
                              text=self._R.manualDescriptionText)
            v -= 30
            # t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.6,1.0,0.6),scale=0.7,
            #                   size=(0,0),maxWidth=cWidth*0.9,
            #                   hAlign='center',vAlign='center',
            #                   text=self._R.worksBetweenAllPlatformsText)
            v -= 70
            t = bs.textWidget(parent=c,position=(cWidth*0.5-260,v),
                              color=(0.6,1.0,0.6),scale=1.0,
                              size=(0,0),maxWidth=200,
                              hAlign='right',vAlign='center',
                              text=self._R.manualAddressText)
            t = bs.textWidget(parent=c,editable=True,description=self._R.manualAddressText,
                              position=(cWidth*0.5-240,v-30),text=lastAddr,
                              vAlign='center',scale=1.0, size=(530,60))

            v -= 110
            
            def _connect(textWidget):
                addr = bs.textWidget(query=textWidget)
                bs.getConfig()['Last Manual Party Connect Address'] = addr # store for later
                bs.writeConfig()
                #bs.screenMessage('WOULD CONNECT TO: \''+addr+"'")
                bsInternal._connectToParty(addr)
                
            b = bs.buttonWidget(parent=c,size=(300,70),label=self._R.manualConnectText,
                                position=(cWidth*0.5-150,v),autoSelect=True,
                                onActivateCall=bs.Call(_connect,t))
            bs.textWidget(edit=t,onReturnPressCall=b.activate)
            v -= 45
            
            ts = 0.85
            tspc = 25

            #v -= 35
            def _safeSetText(t,val,success=True):
                if t.exists(): bs.textWidget(edit=t,text=val,color=(0,1,0) if success else (1,1,0))

            # this currently doesn't work from china since we go through a reverse proxy there
            env = bs.getEnvironment()
            doInternetCheck = False if env['platform'] == 'android' and env['subplatform'] == 'alibaba' else True
            
            def doIt(v,c):
                if not c.exists(): return

                bs.playSound(bs.getSound('swish'))
                t = bs.textWidget(parent=c,position=(cWidth*0.5-10,v),color=(0.6,1.0,0.6),scale=ts,
                                  size=(0,0),maxWidth=cWidth*0.45,flatness=1.0,
                                  hAlign='right',vAlign='center',
                                  text=self._R.manualYourLocalAddressText)
                t = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.5,0.5,0.5),scale=ts,
                                  size=(0,0),maxWidth=cWidth*0.45,flatness=1.0,
                                  hAlign='left',vAlign='center',
                                  text=self._R.checkingText)

                class AddrFetchThread(threading.Thread):
                    def __init__(self,window,textWidget):
                        threading.Thread.__init__(self)
                        #self._data = bsUtils.GameThreadData()
                        #self._data.textWidget = textWidget
                        self._window = window
                        self._textWidget = textWidget
                    def run(self):
                        try:
                            # fixme - update this to work with IPv6 at some point..
                            import socket
                            val = ([(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1])
                            bs.callInGameThread(bs.Call(_safeSetText,self._textWidget,val))
                        except Exception,e:
                            errStr = str(e)
                            if 'Network is unreachable' in errStr:
                                bs.callInGameThread(bs.Call(_safeSetText,self._textWidget,self._window._R.noConnectionText,False))
                            else:
                                bs.callInGameThread(bs.Call(_safeSetText,self._textWidget,self._window._R.addressFetchErrorText,False))
                                bs.callInGameThread(bs.Call(bs.printError,'error in AddrFetchThread: '+str(e)))
                AddrFetchThread(self,t).start()
                
                v -= tspc
                t = bs.textWidget(parent=c,position=(cWidth*0.5-10,v),color=(0.6,1.0,0.6),scale=ts,
                                  size=(0,0),maxWidth=cWidth*0.45,flatness=1.0,
                                  hAlign='right',vAlign='center',
                                  text=self._R.manualYourAddressFromInternetText)

                tAddr = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.5,0.5,0.5),scale=ts,
                                  size=(0,0),maxWidth=cWidth*0.45,
                                      hAlign='left',vAlign='center',flatness=1.0,
                                      text=self._R.checkingText)
                v -= tspc
                t = bs.textWidget(parent=c,position=(cWidth*0.5-10,v),color=(0.6,1.0,0.6),scale=ts,
                                  size=(0,0),maxWidth=cWidth*0.45,flatness=1.0,
                                  hAlign='right',vAlign='center',
                                  text=self._R.manualJoinableFromInternetText)

                tAccessible = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(0.5,0.5,0.5),scale=ts,
                                            size=(0,0),maxWidth=cWidth*0.45,flatness=1.0,
                                            hAlign='left',vAlign='center',
                                            text=self._R.checkingText)
                v -= 28
                tAccessibleExtra = bs.textWidget(parent=c,position=(cWidth*0.5,v),color=(1,0.5,0.2),scale=0.7,
                                                 size=(0,0),maxWidth=cWidth*0.9,flatness=1.0,
                                                 hAlign='center',vAlign='center',
                                                 text='')

                self._doingAccessCheck = False
                self._accessCheckCount = 0 # cap our refreshes eventually..
                self._tabData['accessCheckTimer'] = bs.Timer(10000,bs.WeakCall(self._accessCheckUpdate,tAddr,tAccessible,tAccessibleExtra),
                                                             repeat=True,timeType='real')
                self._accessCheckUpdate(tAddr,tAccessible,tAccessibleExtra)  # kick initial off

                if checkButton.exists():
                    checkButton.delete()
                
            if doInternetCheck:
                checkButton = b = bs.textWidget(parent=c, size=(250,60), text=self._R.showMyAddressText,
                                                vAlign='center',hAlign='center', clickActivate=True,
                                                position=(cWidth*0.5 - 125,v-30), autoSelect=True,
                                                color=(0.5,0.9,0.5),
                                                scale=0.8,
                                                selectable=True,
                                                onActivateCall=bs.Call(doIt,v,c))
                
    def _accessCheckUpdate(self,tAddr,tAccessible,tAccessibleExtra):
        # if we don't have an outstanding query, start one..
        if not self._doingAccessCheck and self._accessCheckCount < 100:
            self._doingAccessCheck = True
            self._accessCheckCount += 1
            self._tAddr = tAddr
            self._tAccessible = tAccessible
            self._tAccessibleExtra = tAccessibleExtra
            bsUtils.serverGet('bsAccessCheck',{},callback=bs.WeakCall(self._onAccessibleResponse))
        
    def _onAccessibleResponse(self,data):
        tAddr = self._tAddr
        tAccessible = self._tAccessible
        tAccessibleExtra = self._tAccessibleExtra
        self._doingAccessCheck = False
        colorBad = (1,1,0)
        colorGood = (0,1,0)
        if data is None or 'address' not in data or 'accessible' not in data:
            if tAddr.exists(): bs.textWidget(edit=tAddr,text=self._R.noConnectionText,color=colorBad)
            if tAccessible.exists(): bs.textWidget(edit=tAccessible,text=self._R.noConnectionText,color=colorBad)
            if tAccessibleExtra.exists(): bs.textWidget(edit=tAccessibleExtra,text='',color=colorBad)
            return
        if tAddr.exists(): bs.textWidget(edit=tAddr,text=data['address'],color=colorGood)
        if tAccessible.exists():
            if data['accessible']:
                bs.textWidget(edit=tAccessible,text=self._R.manualJoinableYesText,color=colorGood)
                if tAccessibleExtra.exists(): bs.textWidget(edit=tAccessibleExtra,text='',color=colorGood)
            else:
                bs.textWidget(edit=tAccessible,text=self._R.manualJoinableNoWithAsteriskText,color=colorBad)
                if tAccessibleExtra.exists(): bs.textWidget(edit=tAccessibleExtra,text=self._R.manualRouterForwardingText.replace('${PORT}',str(bsInternal._getGamePort())),color=colorBad)
        
            
    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._backButton: selName = 'Back'
            elif sel in self._tabButtons.values():
                selName = 'Tab:'+self._tabButtons.keys()[self._tabButtons.values().index(sel)]
            elif sel == self._tabContainer: selName = 'TabContainer'
            else: raise Exception("unrecognized selection: "+str(sel))
            gWindowStates[self.__class__.__name__] = {'selName':selName,'tab':self._currentTab}
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]['selName']
            except Exception: selName = None
            #try: currentTab = gWindowStates[self.__class__.__name__]['tab']
            try: currentTab = bs.getConfig()['Gather Tab']
            except Exception: currentTab = None
            if currentTab is None or currentTab not in self._tabButtons: currentTab = 'about'
            self._setTab(currentTab)
            if selName == 'Back': sel = self._backButton
            elif selName == 'TabContainer': sel = self._tabContainer
            elif type(selName) is str and selName.startswith('Tab:'): sel = self._tabButtons[selName.split(':')[-1]]
            else: sel = self._tabButtons[currentTab]
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)
            
    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()

class PartyWindow(Window):

    def __del__(self):
        bsInternal._setPartyWindowOpen(False)
        
    def __init__(self,origin=(0,0)):
        bsInternal._setPartyWindowOpen(True)
        self._R = bs.getResource('partyWindow')
        self._width = 500
        self._height = 365 if gSmallUI else 480 if gMedUI else 600
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition='inScale',
                                              color=(0.40,0.55,0.20),
                                              onOutsideClickCall=self.closeWithSound,
                                              scaleOriginStackOffset=origin,
                                              scale=2.0 if gSmallUI else 1.35 if gMedUI else 1.0,
                                              stackOffset=(0,-10) if gSmallUI else (240,0) if gMedUI else (330,20))

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,scale=0.5,position=(40,self._height-40),size=(50,50),
                                             label='',onActivateCall=self.close,autoSelect=True,
                                             color=(0.45,0.63,0.15),
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)
        
        self._titleText = bs.textWidget(parent=self._rootWidget,scale=0.9,color=(0.5,0.7,0.5),text=self._R.titleText,
                                      size=(0,0),position=(self._width*0.5,self._height-29),
                                      maxWidth=self._width*0.7,hAlign='center',vAlign='center')

        self._emptyStr = bs.textWidget(parent=self._rootWidget,scale=0.75,
                                       size=(0,0),position=(self._width*0.5,self._height-65),
                                       maxWidth=self._width*0.85,hAlign='center',vAlign='center')

        self._scrollWidth = self._width-50
        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,size=(self._scrollWidth,self._height-200),position=(30,80),color=(0.4,0.6,0.3))
        self._columnWidget = bs.columnWidget(parent=self._scrollWidget)

        self._chatTexts = []
        
        # add all existing messages
        msgs = bsInternal._getChatMessages()
        for msg in msgs:
            self._addMsg(msg)
            
        self._textField = t = bs.textWidget(parent=self._rootWidget,editable=True,size=(530,40),position=(44,39),
                                            text='',maxWidth=494,shadow=0.3,flatness=1.0,
                                            description=self._R.chatMessageText,autoSelect=True,vAlign='center',cornerScale=0.7)

        bs.widget(edit=self._scrollWidget,autoSelect=True,leftWidget=self._cancelButton,upWidget=self._cancelButton,downWidget=self._textField)
        bs.widget(edit=self._columnWidget,autoSelect=True,upWidget=self._cancelButton,downWidget=self._textField)
        bs.containerWidget(edit=self._rootWidget,selectedChild=t)
        b = bs.buttonWidget(parent=self._rootWidget,size=(50,35),label=self._R.sendText,buttonType='square',autoSelect=True,
                            position=(self._width-70,35),onActivateCall=self._sendChatMessage)
        bs.textWidget(edit=t,onReturnPressCall=b.activate)

        self._nameWidgets = []
        self._roster = None
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),repeat=True,timeType='real')
        self._update()

    def onChatMessage(self,msg):
        self._addMsg(msg)
    
    def _addMsg(self,msg):
        t = bs.textWidget(parent=self._columnWidget,text=msg,hAlign='left',vAlign='center',size=(0,13),
                          scale=0.55,maxWidth=self._scrollWidth*0.94,shadow=0.3,flatness=1.0)
        self._chatTexts.append(t)
        if len(self._chatTexts) > 40:
            first = self._chatTexts.pop(0)
            first.delete()
        bs.containerWidget(edit=self._columnWidget,visibleChild=t)
        
    def _update(self):

        roster = bsInternal._getParty()
        
        if roster != self._roster:
            
            self._roster = roster

            # clear out old
            for w in self._nameWidgets: w.delete()
            self._nameWidgets = []
            if len(self._roster) == 0:
                topSectionHeight = 60
                bs.textWidget(edit=self._emptyStr,text=self._R.emptyText)
                bs.scrollWidget(edit=self._scrollWidget,size=(self._width-50,self._height-topSectionHeight-110),position=(30,80))
            else:
                columns = 1 if len(self._roster) == 1 else 2 if len(self._roster) == 2 else 3
                rows = int(math.ceil(float(len(self._roster))/columns))
                cWidth = (self._width*0.9)/max(3,columns)
                cWidthTotal = cWidth*columns
                cHeight = 24
                cHeightTotal = cHeight*rows
                for y in range(rows):
                    for x in range(columns):
                        index = y*columns+x
                        if index < len(self._roster):
                            tScale = 0.65
                            pos = (self._width*0.53-cWidthTotal*0.5+cWidth*x,self._height-65-cHeight*y)
                            self._nameWidgets.append(bs.textWidget(parent=self._rootWidget,position=pos,scale=tScale,size=(0,0),maxWidth=cWidth*0.85,
                                                                   color=(1,1,1) if index==0 else (1,1,1),
                                                                   text=self._roster[index]['displayString'],hAlign='left',vAlign='center'))
                            if index == 0:
                                tw = min(cWidth*0.85,bs.getStringWidth(self._roster[index]['displayString'])*tScale)
                                self._nameWidgets.append(bs.textWidget(parent=self._rootWidget,position=(pos[0]+tw+1,pos[1]-0.5),size=(0,0),hAlign='left',vAlign='center',
                                                                       maxWidth=cWidth*0.96-tw,color=(0.1,1,0.1,0.5),text=self._R.hostText,scale=0.4,shadow=0.1,flatness=1.0))
                bs.textWidget(edit=self._emptyStr,text='')
                bs.scrollWidget(edit=self._scrollWidget,size=(self._width-50,max(100,self._height-139-cHeightTotal)),position=(30,80))
            
            
            
    def _sendChatMessage(self):
        bsInternal._chatMessage(bs.textWidget(query=self._textField))
        bs.textWidget(edit=self._textField,text='')
        
    def close(self):
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
    def closeWithSound(self):
        bs.playSound(bs.getSound('swish'))
        self.close()
        
gPartyWindow = None
def onPartyIconActivate(origin):
    global gPartyWindow
    bs.playSound(bs.getSound('swish'))
    # if it exists, dismiss it; otherwise make a new one
    if gPartyWindow is not None and gPartyWindow() is not None: gPartyWindow().close()
    else: gPartyWindow = weakref.ref(PartyWindow(origin=origin))
        
class OnScreenKeyboardWindow(Window):

    def __init__(self, textWidget, label, maxChars):

        self._targetText = textWidget
        
        self._width = 700
        self._height = 400

        topExtra = 20 if gSmallUI else 0
        target = self._targetText.getScreenSpaceCenter()
        self._rootWidget = bs.containerWidget(size=(self._width,self._height+topExtra),transition='inScale',
                                              scaleOriginStackOffset=self._targetText.getScreenSpaceCenter(),
                                              scale=2.0 if gSmallUI else 1.5 if gMedUI else 1.0,
                                              stackOffset=(0,0) if gSmallUI else (0,0) if gMedUI else (0,0))
        self._doneButton = bs.buttonWidget(parent=self._rootWidget,position=(self._width-200,44),size=(140,60),
                                           autoSelect=True,
                                           label=bs.getResource('doneText'),
                                           onActivateCall=self._done)
        bs.containerWidget(edit=self._rootWidget,onCancelCall=self._cancel,startButton=self._doneButton)
        
        bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height - 41),size=(0,0),scale=0.95,
                      text=label+':',maxWidth=self._width-140,color=gTitleColor,hAlign='center',vAlign='center')
        
        self._textField = bs.textWidget(parent=self._rootWidget,position=(70,self._height - 116),maxChars=maxChars,
                                        text=bs.textWidget(query=self._targetText),onReturnPressCall=self._done,
                                        autoSelect=True,
                                        size=(self._width-140,55),vAlign='center',editable=True,maxWidth=self._width-175,
                                        forceInternalEditing=True,alwaysShowCarat=True)

        self._shiftButton = None
        self._numModeButton = None
        self._charKeys = []
        self._mode = 'normal'
        
        h = 79
        v = self._height - 180
        keyWidth = 46
        keyHeight = 46
        self._keyColorLit = keyColorLit = (1.4,1.2,1.4)
        self._keyColor = keyColor = (0.69,0.6,0.74)
        self._keyColorDark = keyColorDark = (0.55,0.55,0.71)
        keyTextColor = (1,1,1)
        rowStarts = (69,95,151)

        self._clickSound = bs.getSound('click01')
        
        # kill prev char keys
        for key in self._charKeys:
            key.delete()
        self._charKeys = []

        # dummy data just used for row/column lengths... we dont actually set things until refresh
        chars = [('q','u','e','r','t','y','u','i','o','p'),
                 ('a','s','d','f','g','h','j','k','l'),
                 ('z','x','c','v','b','n','m')]
        
        for rowNum, row in enumerate(chars):
            h = rowStarts[rowNum]
            # shift key before row 3
            if rowNum == 2:
                self._shiftButton = bs.buttonWidget(parent=self._rootWidget,position=(h-keyWidth*2.0,v),size=(keyWidth*1.7,keyHeight),autoSelect=True,
                                                    textColor=keyTextColor,color=keyColorDark,label=bs.getSpecialChar('shift'),
                                                    enableSound=False,
                                                    extraTouchBorderScale=0.3,
                                                    buttonType='square',
                )
            
            for char in row:
                b = bs.buttonWidget(parent=self._rootWidget,position=(h,v),size=(keyWidth,keyHeight),autoSelect=True,
                                    enableSound=False,
                                    textColor=keyTextColor,color=keyColor,label='',buttonType='square',
                                    extraTouchBorderScale=0.1,
                )
                self._charKeys.append(b)
                h += keyWidth+10

            # add delete key at end of third row
            if rowNum == 2:
                b = bs.buttonWidget(parent=self._rootWidget,position=(h+4,v),size=(keyWidth*1.8,keyHeight),autoSelect=True,
                                    enableSound=False,
                                    repeat=True,
                                    textColor=keyTextColor,color=keyColorDark,label=bs.getSpecialChar('delete'),
                                    buttonType='square',onActivateCall=self._del)
            v -= (keyHeight+9)
            # do space bar and stuff..
            if rowNum == 2:
                if self._numModeButton is None:
                    self._numModeButton = bs.buttonWidget(parent=self._rootWidget,position=(112,v-8),size=(keyWidth*2,keyHeight+5),
                                                          enableSound=False,
                                                          buttonType='square',
                                                          extraTouchBorderScale=0.3,
                                                          autoSelect=True, textColor=keyTextColor,color=keyColorDark,label='',
                                                          # onActivateCall=self._numMode
                    )
                b1 = self._numModeButton
                b2 = bs.buttonWidget(parent=self._rootWidget,position=(210,v-12),size=(keyWidth*6.1,keyHeight+15),
                                     extraTouchBorderScale=0.3,enableSound=False,
                                     autoSelect=True, textColor=keyTextColor,color=keyColorDark,label=bs.getResource('spaceKeyText'),
                                     onActivateCall=bs.Call(self._typeChar,' '))
                bs.widget(edit=b1,rightWidget=b2)
                bs.widget(edit=b2,leftWidget=b1,rightWidget=self._doneButton)
                bs.widget(edit=self._doneButton,leftWidget=b2)

        bs.containerWidget(edit=self._rootWidget,selectedChild=self._charKeys[14])
                
        self._refresh()
        
    def _refresh(self):

        if self._mode in ['normal','caps']:
            chars = ['q','w','e','r','t','y','u','i','o','p',
                     'a','s','d','f','g','h','j','k','l',
                     'z','x','c','v','b','n','m']
            if self._mode == 'caps':
                chars = [c.upper() for c in chars]
            bs.buttonWidget(edit=self._shiftButton,color=self._keyColorLit if self._mode == 'caps' else self._keyColorDark,
                            label=bs.getSpecialChar('shift'),onActivateCall=self._shift)
            bs.buttonWidget(edit=self._numModeButton,label='123#&*',onActivateCall=self._numMode)
        elif self._mode == 'num':
            chars = ['1','2','3','4','5','6','7','8','9','0',
                     '-','/',':',';','(',')','$','&','@',
                     '"','.',',','?','!','\'','_']
            bs.buttonWidget(edit=self._shiftButton,color=self._keyColorDark,label='',
                            onActivateCall=self._nullPress)
            bs.buttonWidget(edit=self._numModeButton,label='abc',onActivateCall=self._abcMode)
        
        for i,b in enumerate(self._charKeys):
            bs.buttonWidget(edit=b,label=chars[i],
                            onActivateCall=bs.Call(self._typeChar,chars[i]))

    def _nullPress(self):
        bs.playSound(self._clickSound)
        pass
    def _abcMode(self):
        bs.playSound(self._clickSound)
        self._mode = 'normal'
        self._refresh()
        
    def _numMode(self):
        bs.playSound(self._clickSound)
        self._mode = 'num'
        self._refresh()
                    
    def _shift(self):
        bs.playSound(self._clickSound)
        if self._mode == 'normal': self._mode = 'caps'
        elif self._mode == 'caps': self._mode = 'normal'
        # self._shiftPressed = True
        self._refresh()
        
    def _del(self):
        bs.playSound(self._clickSound)
        t = bs.textWidget(query=self._textField)
        t = t[:-1]
        bs.textWidget(edit=self._textField,text=t)
        
    def _typeChar(self,char):
        bs.playSound(self._clickSound)
        # operate in unicode so we don't do anything funky like chop utf-8 chars in half
        t = bs.textWidget(query=self._textField)
        t += char
        bs.textWidget(edit=self._textField,text=t)
        # if we were caps, go back
        if self._mode == 'caps':
            self._mode = 'normal'
        self._refresh()
        
    def _cancel(self):
        bs.playSound(bs.getSound('swish'))
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
    def _done(self):

        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
        if self._targetText.exists():
            bs.textWidget(edit=self._targetText,text=bs.textWidget(query=self._textField))
            
        
class StoreWindow(Window):

    def _updateGetTicketsButtonPos(self):
        if self._getTicketsButton.exists():
            p = (self._width-252-(47 if gSmallUI and bsInternal._isPartyIconVisible() else 0),self._height-70)
            bs.buttonWidget(edit=self._getTicketsButton,position=p)
        
    def __init__(self,transition='inRight',modal=False,showTab=None,
                 onCloseCall=None,backLocation=None,originWidget=None):

        bsInternal._setAnalyticsScreen('Store Window')
        
        # if they provided an origin-widget, scale up from that
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
        
        self._backLocation = backLocation
        self._onCloseCall = onCloseCall
        self._showTab = showTab
        self._modal = modal
        self._width = 1040
        self._height = 578 if gSmallUI else 675 if gMedUI else 800
        self._currentTab = None
        extraTop = 30 if gSmallUI else 0
        
        self._request = None
        self._R = bs.getResource('store')
        self._lastBuyTime = 0

        self._rootWidget = bs.containerWidget(size=(self._width,self._height+extraTop),transition=transition,
                                              scale=1.3 if gSmallUI else 0.96 if gMedUI else 0.8,
                                              scaleOriginStackOffset=scaleOrigin,
                                              stackOffset=(0,-5) if gSmallUI else (0,0) if gMedUI else (0,0))

        self._backButton = backButton = b = bs.buttonWidget(parent=self._rootWidget,position=(70,self._height-74),size=(140,60),scale=1.1,
                                                            autoSelect=True,
                                                            label=bs.getResource('doneText' if self._modal else 'backText'),
                                                            buttonType=None if self._modal else 'back',
                                                            onActivateCall=self._back)
        bs.containerWidget(edit=self._rootWidget,cancelButton=b)

        self._getTicketsButton = b = bs.buttonWidget(parent=self._rootWidget,
                                                     size=(210,65),
                                                     onActivateCall=self._onGetMoreTicketsPress,
                                                     autoSelect=True,
                                                     scale=0.9,
                                                     textScale=1.4,
                                                     leftWidget=self._backButton,
                                                     color=(0.7,0.5,0.85),
                                                     textColor=(1,0.5,0),
                                                     label=bs.getResource('getTicketsWindow.titleText'))
        
        # move this dynamically to keep it out of the way of the party icon :-(
        self._updateGetTicketsButtonPos()
        self._getTicketPosUpdateTimer = bs.Timer(1000,bs.WeakCall(self._updateGetTicketsButtonPos),repeat=True,timeType='real')
        bs.widget(edit=self._backButton,rightWidget=self._getTicketsButton)
        self._ticketTextUpdateTimer = bs.Timer(1000,bs.WeakCall(self._updateTicketsText),timeType='real',repeat=True)
        self._updateTicketsText()

        env = bs.getEnvironment()
        if env['platform'] in ['mac','ios'] and env['subplatform'] == 'appstore':
            # b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-240,60),size=(230,60),scale=0.7,
            b = bs.buttonWidget(parent=self._rootWidget,position=(self._width*0.5-70,16),size=(230,50),scale=0.65,
                                onActivateCall=bs.WeakCall(self._restorePurchases),
                                #color=(0.45,0.4,0.5),
                                color=(0.35,0.3,0.4),
                                selectable=False,
                                textColor=(0.55,0.5,0.6),
                                label=bs.getResource('getTicketsWindow.restorePurchasesText'))


        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-44),size=(0,0),
                          color=gTitleColor,scale=1.5,hAlign="center",vAlign="center",
                          text=bs.getResource('storeText'),
                          maxWidth=420)

        if not self._modal and gDoAndroidNav:
            bs.buttonWidget(edit=self._backButton,buttonType='backSmall',size=(60,60),label=bs.getSpecialChar('back'))
            bs.textWidget(edit=t,hAlign='left',position=(153,self._height-44))

        scrollBufferH = 130
        tabBufferH = 250
        
        tabsDef = [['extras',self._R.extrasText],
                   ['maps',self._R.mapsText],
                   ['minigames',self._R.miniGamesText],
                   ['characters',self._R.charactersText],
                   ['icons',self._R.iconsText]]

        tabResults = _createTabButtons(self._rootWidget,tabsDef,pos=(tabBufferH*0.5,self._height - 130),
                                             size=(self._width-tabBufferH,50),onSelectCall=self._setTab,returnExtraInfo=True)

        self._purchasableCountWidgets = {}
        
        # create our purchasable-items tags and have them update over time..
        for i,tab in enumerate(tabsDef):
            pos = tabResults['positions'][i]
            size = tabResults['sizes'][i]
            button = tabResults['buttonsIndexed'][i]
            rad = 10
            center = (pos[0]+0.1*size[0],pos[1]+0.9*size[1])
            img = bs.imageWidget(parent=self._rootWidget,position=(center[0]-rad*1.04,center[1]-rad*1.15),size=(rad*2.2,rad*2.2),
                           texture=bs.getTexture('circleShadow'),color=(1,0,0))
            txt = bs.textWidget(parent=self._rootWidget,position=center,size=(0,0),hAlign='center',vAlign='center',
                                maxWidth=1.4*rad,scale=0.6,shadow=1.0,flatness=1.0)
            rad = 20
            saleImg = bs.imageWidget(parent=self._rootWidget,position=(center[0]-rad,center[1]-rad),size=(rad*2,rad*2),
                                     drawController=button,
                                     texture=bs.getTexture('circleZigZag'),color=(0.5,0,1.0))
            saleTitleText = bs.textWidget(parent=self._rootWidget,position=(center[0],center[1]+0.24*rad),size=(0,0),hAlign='center',vAlign='center',
                                          drawController=button,
                                          maxWidth=1.4*rad,scale=0.6,shadow=0.0,flatness=1.0,color=(0,1,0))
            saleTimeText = bs.textWidget(parent=self._rootWidget,position=(center[0],center[1]-0.29*rad),size=(0,0),hAlign='center',vAlign='center',
                                     drawController=button,
                                     maxWidth=1.4*rad,scale=0.4,shadow=0.0,flatness=1.0,color=(0,1,0))
            self._purchasableCountWidgets[tab[0]] = {'img':img,
                                                     'text':txt,
                                                     'saleImg':saleImg,
                                                     'saleTitleText':saleTitleText,
                                                     'saleTimeText':saleTimeText}
        self._tabUpdateTimer = bs.Timer(1000,bs.WeakCall(self._updateTabs),timeType='real',repeat=True)
        self._updateTabs()

        self._tabButtons = tabResults['buttons']
        
        if self._getTicketsButton is not None:
            lastTabButton = self._tabButtons[tabsDef[-1][0]]
            bs.widget(edit=self._getTicketsButton,downWidget=lastTabButton)
            bs.widget(edit=lastTabButton,upWidget=self._getTicketsButton,rightWidget=self._getTicketsButton)
            
        self._scrollWidth = self._width-scrollBufferH
        self._scrollHeight = self._height-180

        self._scrollWidget = None
        self._statusTextWidget = None
        self._restoreState()

    def _restorePurchases(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
        else:
            bsInternal._restorePurchases()
        
    def _updateTabs(self):
        for tabName,tabData in self._purchasableCountWidgets.items():
            saleTime = _getAvailableSaleTime(tabName)

            if saleTime is not None:
                bs.textWidget(edit=tabData['saleTitleText'],text=bs.getResource('store.saleText'))
                bs.textWidget(edit=tabData['saleTimeText'],text=bsUtils.getTimeString(saleTime,centi=False))
                bs.imageWidget(edit=tabData['saleImg'],opacity=1.0)
                count = 0
            else:
                bs.textWidget(edit=tabData['saleTitleText'],text='')
                bs.textWidget(edit=tabData['saleTimeText'],text='')
                bs.imageWidget(edit=tabData['saleImg'],opacity=0.0)
                count = _getAvailablePurchaseCount(tabName)

            if count > 0:
                bs.textWidget(edit=tabData['text'],text=str(count))
                bs.imageWidget(edit=tabData['img'],opacity=1.0)
            else:
                bs.textWidget(edit=tabData['text'],text='')
                bs.imageWidget(edit=tabData['img'],opacity=0.0)
        
    def _updateTicketsText(self):
        if bsInternal._getAccountState() == 'SIGNED_IN':
            s = bs.getSpecialChar('ticket')+str(bsInternal._getAccountTicketCount())
        else:
            #s = bs.getSpecialChar('ticket')+'?'
            s = bs.getResource('getTicketsWindow.titleText')
        bs.buttonWidget(edit=self._getTicketsButton,label=s)
        
    def _setTab(self,tab):

        if self._currentTab == tab: return
        self._currentTab = tab

        # we wanna preserve our current tab between runs
        bs.getConfig()['Store Tab'] = tab
        bs.writeConfig()
        
        # update tab colors based on which is selected
        _updateTabButtonColors(self._tabButtons,tab)

        # (re)create scroll widget
        if self._scrollWidget is not None and self._scrollWidget.exists():
            self._scrollWidget.delete()

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,highlight=False,position=((self._width-self._scrollWidth)*0.5,self._height-self._scrollHeight-79-48),size=(self._scrollWidth,self._scrollHeight))

        # stop updating anything that was there
        self._buttonInfos = {}
        self._updateButtonsTimer = None

        # so we can still select root level widgets with controllers
        bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)

        # show status over top..
        if self._statusTextWidget is not None and self._statusTextWidget.exists():
            self._statusTextWidget.delete()
        self._statusTextWidget = bs.textWidget(parent=self._rootWidget,
                                               position=(self._width*0.5-bs.getStringWidth(self._R.loadingText)*0.5,self._height*0.5),size=(0,0),
                                               color=(1,0.7,1,0.5),hAlign="left",vAlign="center",
                                               text=self._R.loadingText,maxWidth=self._scrollWidth*0.9)
        self._statusTextWidgetUpdateTimer = bs.Timer(500,bs.WeakCall(self._updateStatusText),repeat=True,timeType='real')
        self._statusTextDots = 1


        class _Request(object):
            def __init__(self,window):
                self._window = weakref.ref(window)
                data = {'tab':tab}
                bs.realTimer(100,bs.WeakCall(self._onResponse,data))
            def _onResponse(self,data):
                window = self._window()
                if window is not None and (window._request is self):
                    window._request = None
                    window._onResponse(data)

        # kick off a server request
        self._request = _Request(self)
        
    def _updateStatusText(self):
        if self._statusTextWidget.exists():
            bs.textWidget(edit=self._statusTextWidget,
                          text=self._R.loadingText+'.'*self._statusTextDots)
            self._statusTextDots += 1
            if self._statusTextDots > 3:
                self._statusTextDots = 0

    # actually start the purchase locally..
    def _purchaseCheckResult(self,item,isTicketPurchase,result):
        if result is None:
            bs.playSound(bs.getSound('error'))
            bs.screenMessage(bs.getResource('internal.unavailableNoConnectionText'),color=(1,0,0))
        else:
            if isTicketPurchase:
                price = bsInternal._getAccountMiscReadVal('price.'+item, None)
                if price is None or type(price) not in (int,long) or price <= 0:
                    print 'Error; got invalid local price of',price,'for item',item
                    bs.playSound(bs.getSound('error'))
                else:
                    bs.playSound(bs.getSound('click01'))
                    bsInternal._inGamePurchase(item, price)
            # real in-app purchase
            else:
                if result['allow']:
                    bsInternal._purchase(item)
                else:
                    if result['reason'] == 'versionTooOld':
                        bs.playSound(bs.getSound('error'))
                        bs.screenMessage(bs.getResource('getTicketsWindow.versionTooOldText'),color=(1,0,0))
                    else:
                        bs.playSound(bs.getSound('error'))
                        bs.screenMessage(bs.getResource('getTicketsWindow.unavailableText'),color=(1,0,0))

    def _doPurchaseCheck(self,item,isTicketPurchase=False):
        # here we ping the server to ask if it's valid for us to purchase this..
        # (better to fail now than after we've paid locally)
        env = bs.getEnvironment()
        bsUtils.serverGet('bsAccountPurchaseCheck',{'item':item,
                                                    'platform':env['platform'],
                                                    'subplatform':env['subplatform'],
                                                    'version':env['version'],
                                                    'buildNumber':env['buildNumber'],
                                                    'purchaseType':'ticket' if isTicketPurchase else 'real'},
                          callback=bs.WeakCall(self._purchaseCheckResult,item,isTicketPurchase))
        
    def _buy(self,item):
        # prevent pressing buy within a few seconds of the last press
        # (gives the buttons time to disable themselves and whatnot)
        t = bs.getRealTime()
        if t - self._lastBuyTime < 2000:
            bs.playSound(bs.getSound('error'))
        else:
            if bsInternal._getAccountState() != 'SIGNED_IN':
                showSignInPrompt()
            else:
                # pros is an actual IAP; the rest are ticket purchases.
                if item == 'pro':
                    bs.playSound(bs.getSound('click01'))
                    self._lastBuyTime = t
                    # purchase either pro or pro_sale depending on whether there is a sale going on..
                    #bsInternal._purchase('pro' if _getAvailableSaleTime('extras') is None else 'pro_sale')
                    self._doPurchaseCheck('pro' if _getAvailableSaleTime('extras') is None else 'pro_sale')
                else:
                    # def doIt():
                    self._lastBuyTime = t
                    price = bsInternal._getAccountMiscReadVal('price.'+item,None)
                    ourTickets = bsInternal._getAccountTicketCount()
                    if price is not None and ourTickets < price:
                        bs.playSound(bs.getSound('error'))
                        showGetTicketsPrompt()
                    else:
                        def doIt():
                            self._doPurchaseCheck(item,isTicketPurchase=True)
                        bs.playSound(bs.getSound('swish'))
                        ConfirmWindow(bs.getResource('store.purchaseConfirmText').replace('${ITEM}',_getStoreItemNameTranslated(item)),width=400,height=120,
                                      action=doIt,okText=bs.getResource('store.purchaseText',fallback='okText'))
                        #PurchaseConfirmWindow()
                        #print 'WOULD DO POPUP'
                    # else:
                    #     self._lastBuyTime = t
                    #     price = bsInternal._getAccountMiscReadVal('price.'+item,None)
                    #     ourTickets = bsInternal._getAccountTicketCount()
                    #     if price is not None and ourTickets < price:
                    #         bs.playSound(bs.getSound('error'))
                    #         showGetTicketsPrompt()
                    #     else:
                    #         self._doPurchaseCheck(item,isTicketPurchase=True)

    def _printAlreadyOwn(self,charName):
        bs.screenMessage(self._R.alreadyOwnText.replace('${NAME}',charName),color=(1,0,0))
        bs.playSound(bs.getSound('error'))

    def _updateButtons(self):
        import datetime
        salesRaw = bsInternal._getAccountMiscReadVal('sales',{})
        sales = {}
        try:
            # look at the current set of sales; filter any with time remaining..
            for saleItem, saleInfo in salesRaw.items():
                toEnd = (datetime.datetime.utcfromtimestamp(saleInfo['e']) - datetime.datetime.utcnow()).total_seconds()
                if toEnd > 0:
                    sales[saleItem] = {'toEnd':toEnd,'originalPrice':saleInfo['op']}
        except Exception:
            bs.printException("Error parsing sales")
        
        for bType,bInfo in self._buttonInfos.items():

            if bType in ['upgrades.pro','pro']: purchased = bsUtils._havePro()
            else: purchased = bsInternal._getPurchased(bType)

            saleOpacity = 0.0
            saleTitleText = ''
            saleTimeText = ''
            
            if purchased:
                titleColor=(0.8,0.7,0.9,1.0)
                color = (0.63,0.55,0.78)
                call = bs.WeakCall(self._printAlreadyOwn,bInfo['name'])
                # priceText = self._R.youOwnThisText
                priceText = ''
                priceTextLeft = ''
                priceTextRight = ''
                showPurchaseCheck = True
                descriptionColor = (0.4,1.0,0.4,0.4)
                priceColor = (0.5,1,0.5,0.3)
            else:
                titleColor=(0.7,0.9,0.7,1.0)
                color = (0.4,0.8,0.1)
                call = bInfo['call'] if 'call' in bInfo else None


                if bType in ['upgrades.pro','pro']:
                    saleTime = _getAvailableSaleTime('extras')
                    if saleTime is not None:
                        price = bsInternal._getPrice('pro')
                        priceTextLeft = price if price is not None else '?'
                        price = bsInternal._getPrice('pro_sale')
                        priceTextRight = price if price is not None else '?'
                        saleOpacity = 1.0
                        priceText = ''
                        saleTitleText = bs.getResource('store.saleText')
                        saleTimeText = bs.getTimeString(saleTime,centi=False)
                    else:
                        price = bsInternal._getPrice('pro')
                        priceText = price if price is not None else '?'
                        priceTextLeft = ''
                        priceTextRight = ''
                    # if price is None: priceText = '??'
                    # else: priceText = price
                else:
                    price = bsInternal._getAccountMiscReadVal('price.'+bType,0)
                    # color button differently if we cant afford this
                    if bsInternal._getAccountState() == 'SIGNED_IN':
                        if bsInternal._getAccountTicketCount() < price:
                            color = (0.6, 0.61, 0.6)
                    priceText = bs.getSpecialChar('ticket')+str(bsInternal._getAccountMiscReadVal('price.'+bType,'?'))
                    priceTextLeft = ''
                    priceTextRight = ''

                    # TESTING:
                    if bType in sales:
                        saleOpacity = 1.0
                        priceTextLeft = bs.getSpecialChar('ticket')+str(sales[bType]['originalPrice'])
                        priceTextRight = priceText
                        priceText = ''
                        saleTitleText = bs.getResource('store.saleText')
                        saleTimeText = bs.getTimeString(int(sales[bType]['toEnd']*1000),centi=False)
                    
                descriptionColor = (0.5,1,0.5)
                priceColor = (1,0.5,0.0,1.0)
                showPurchaseCheck = False

            if 'titleText' in bInfo: bs.textWidget(edit=bInfo['titleText'], color=titleColor)
            if 'purchaseCheck' in bInfo: bs.imageWidget(edit=bInfo['purchaseCheck'],opacity=1.0 if showPurchaseCheck else 0.0)
            if 'priceWidget' in bInfo: bs.textWidget(edit=bInfo['priceWidget'],text=priceText,color=priceColor)
            if 'priceWidgetLeft' in bInfo: bs.textWidget(edit=bInfo['priceWidgetLeft'],text=priceTextLeft)
            if 'priceWidgetRight' in bInfo: bs.textWidget(edit=bInfo['priceWidgetRight'],text=priceTextRight)
            if 'priceSlashWidget' in bInfo: bs.imageWidget(edit=bInfo['priceSlashWidget'],opacity=saleOpacity)
            if 'saleBGWidget' in bInfo: bs.imageWidget(edit=bInfo['saleBGWidget'],opacity=saleOpacity)
            if 'saleTitleWidget' in bInfo: bs.textWidget(edit=bInfo['saleTitleWidget'],text=saleTitleText)
            if 'saleTimeWidget' in bInfo: bs.textWidget(edit=bInfo['saleTimeWidget'],text=saleTimeText)
            if 'button' in bInfo: bs.buttonWidget(edit=bInfo['button'],color=color,onActivateCall=call)
            if 'descriptionText' in bInfo: bs.textWidget(edit=bInfo['descriptionText'],color=descriptionColor)

    def _onResponse(self,data):

        # clear status text..
        if self._statusTextWidget is not None and self._statusTextWidget.exists():
            self._statusTextWidget.delete()
            self._statusTextWidgetUpdateTimer = None
        
        if data is None:
            self._statusTextWidget = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5),size=(0,0),
                                                   scale=1.3,
                                                   transitionDelay=100,
                                                   color=(1,0.3,0.3,1.0),hAlign="center",vAlign="center",
                                                   text=self._R.loadErrorText,maxWidth=self._scrollWidth*0.9)
        else:
            class _Store(object):

                def __init__(self,storeWindow,data,width):

                    self._storeWindow = storeWindow
                    self._width = width
                    self._rows = []
                    storeData = _getStoreLayout()
                    
                    self._tab = data['tab']
                    self._sections = copy.deepcopy(storeData[data['tab']])

                    # pre-calc a few things and add them to store-data
                    for section in self._sections:
                        # if self._tab == 'characters': section['buttonSize'] = (340*0.6,430*0.6)
                        # elif self._tab == 'extras': section['buttonSize'] = (650*0.75,500*0.75)
                        # elif self._tab == 'maps': section['buttonSize'] = (510*0.6,450*0.6)
                        # else: section['buttonSize'] = (450*0.6,450*0.6)
                        if self._tab == 'characters': dummyName = 'characters.foo'
                        elif self._tab == 'extras': dummyName = 'pro'
                        elif self._tab == 'maps': dummyName = 'maps.foo'
                        elif self._tab == 'icons': dummyName = 'icons.foo'
                        else: dummyName = ''
                        section['buttonSize'] = _getStoreItemDisplaySize(dummyName)
                        section['vSpacing'] = -17 if self._tab == 'characters' else 0
                        if 'title' not in section: section['title'] = ''
                        #section['xOffs'] = 200 if self._tab == 'characters' else 170 if self._tab == 'extras' else 0
                        # section['xOffs'] = 100 if (self._tab == 'characters' and not bsInternal._getAccountMiscReadVal('xmas',False)) else 130 if self._tab == 'extras' else 270 if self._tab == 'maps' else 0
                        section['xOffs'] = 130 if self._tab == 'extras' else 270 if self._tab == 'maps' else 0
                        section['yOffs'] = 40 if (self._tab == 'extras' and gSmallUI) else -20 if self._tab == 'icons' else 0
                        
                def instantiate(self,scrollWidget,tabButton):

                    titleSpacing = 40
                    buttonBorder = 20
                    buttonSpacing = 4
                    # buttonVSpacing = -10
                    buttonOffsetH = 40
                    
                    self._height = 80

                    # calc total height
                    for i,section in enumerate(self._sections):
                        if section['title'] != '': self._height += titleSpacing
                        bWidth,bHeight = section['buttonSize']
                        bColumnCount = int(math.floor((self._width-buttonOffsetH-20)/(bWidth+buttonSpacing)))
                        bRowCount = int(math.ceil(float(len(section['items']))/bColumnCount))
                        bHeightTotal = 2*buttonBorder+bRowCount*bHeight+(bRowCount-1)*section['vSpacing']
                        self._height += bHeightTotal

                    c = bs.containerWidget(parent=scrollWidget,scale=1.0,size=(self._width,self._height),background=False)
                    bs.containerWidget(edit=c,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
                    v = self._height - 20

                    if self._tab == 'characters':
                        t = (bs.getResource('store.howToSwitchCharactersText')
                             .replace('${SETTINGS}',bs.getResource('accountSettingsWindow.titleText'))
                             .replace('${PLAYER_PROFILES}',bs.getResource('playerProfilesWindow.titleText')))
                        bs.textWidget(parent=c,text=t,size=(0,0),position=(self._width*0.5,self._height - 28),
                                      hAlign='center',vAlign='center',color=(0.7,1,0.7,0.4),scale=0.7,shadow=0,flatness=1.0,
                                      maxWidth=700,transitionDelay=400)
                    elif self._tab == 'icons':
                        t = (bs.getResource('store.howToUseIconsText')
                             .replace('${SETTINGS}',bs.getResource('mainMenu.settingsText'))
                             .replace('${PLAYER_PROFILES}',bs.getResource('playerProfilesWindow.titleText')))
                        bs.textWidget(parent=c,text=t,size=(0,0),position=(self._width*0.5,self._height - 28),
                                      hAlign='center',vAlign='center',color=(0.7,1,0.7,0.4),scale=0.7,shadow=0,flatness=1.0,
                                      maxWidth=700,transitionDelay=400)
                    elif self._tab == 'maps':
                        t = bs.getResource('store.howToUseMapsText')
                        bs.textWidget(parent=c,text=t,size=(0,0),position=(self._width*0.5,self._height - 28),
                                      hAlign='center',vAlign='center',color=(0.7,1,0.7,0.4),scale=0.7,shadow=0,flatness=1.0,
                                      maxWidth=700,transitionDelay=400)
                        
                    prevRowButtons = None
                    thisRowButtons = []

                    
                    delay = 300
                    for section in self._sections:
                        if section['title'] != '':
                            bs.textWidget(parent=c,position=(60,v-titleSpacing*0.8),size=(0,0),
                                          scale=1.0,
                                          transitionDelay=delay,
                                          color=(0.7,0.9,0.7,1),hAlign="left",vAlign="center",
                                          text=bs.getResource(section['title']),maxWidth=self._width*0.7)
                            v -= titleSpacing
                        delay = max(100,delay-100)
                        v -= buttonBorder
                        bWidth,bHeight = section['buttonSize']
                        bCount = len(section['items'])
                        bColumnCount = int(math.floor((self._width-buttonOffsetH-20)/(bWidth+buttonSpacing)))
                        col = 0
                        for i,itemName in enumerate(section['items']):

                            item = self._storeWindow._buttonInfos[itemName] = {}
                            item['call'] = bs.WeakCall(self._storeWindow._buy,itemName)

                            if 'xOffs' in section: bOffsH2 = section['xOffs']
                            else: bOffsH2 = 0

                            if 'yOffs' in section: bOffsV2 = section['yOffs']
                            else: bOffsV2 = 0

                            bPos = (buttonOffsetH+bOffsH2+(bWidth+buttonSpacing)*col,v-bHeight+bOffsV2)
                            
                            _instantiateStoreItemDisplay(itemName,item,
                                                         parentWidget=c,
                                                         bPos=bPos,
                                                         buttonOffsetH=buttonOffsetH,
                                                         bWidth=bWidth,bHeight=bHeight,
                                                         bOffsH2=bOffsH2,bOffsV2=bOffsV2,
                                                         delay=delay)
                            b = item['button']
                            
                            delay = max(100,delay-100)
                            thisRowButtons.append(b)

                            # wire this button to the equivalent in the previous row
                            if prevRowButtons is not None:
                                if len(prevRowButtons) > col:
                                    bs.widget(edit=b,upWidget=prevRowButtons[col])
                                    bs.widget(edit=prevRowButtons[col],downWidget=b)
                                    # if we're the last button in our row, wire any in the previous row past
                                    # our position to go to us if down is pressed
                                    if col+1 == bColumnCount or i == bCount-1:
                                        for bPrev in prevRowButtons[col+1:]:
                                            bs.widget(edit=bPrev,downWidget=b)
                                else:
                                    bs.widget(edit=b,upWidget=prevRowButtons[-1])
                            else:
                                bs.widget(edit=b,upWidget=tabButton)
                                
                            col += 1
                            if col == bColumnCount or i == bCount-1:
                                prevRowButtons = thisRowButtons
                                thisRowButtons = []
                                col = 0
                                v -= bHeight
                                if i < bCount-1: v -= section['vSpacing']

                        v -= buttonBorder

                    # set a timer to update these buttons periodically as long as we're alive
                    # (so if we buy one it will grey out, etc)
                    self._storeWindow._updateButtonsTimer = bs.Timer(500,bs.WeakCall(self._storeWindow._updateButtons),repeat=True,timeType='real')
                    # also update them immediately
                    self._storeWindow._updateButtons()
                    
            if self._currentTab in ('extras','minigames','characters','maps','icons'):
                store = _Store(self,data,self._scrollWidth)
                store.instantiate(scrollWidget=self._scrollWidget,tabButton=self._tabButtons[self._currentTab])
            else:
                c = bs.containerWidget(parent=self._scrollWidget,scale=1.0,size=(self._scrollWidth,self._scrollHeight*0.95),
                                       background=False)
                bs.containerWidget(edit=c,claimsLeftRight=True,claimsTab=True,selectionLoopToParent=True)
                self._statusTextWidget = bs.textWidget(parent=c,position=(self._scrollWidth*0.5,self._scrollHeight*0.5),size=(0,0),
                                                       scale=1.3,transitionDelay=100,
                                                       color=(1,1,0.3,1.0),hAlign="center",vAlign="center",
                                                       text=self._R.comingSoonText,maxWidth=self._scrollWidth*0.9)

    def _saveState(self):
        try:
            sel = self._rootWidget.getSelectedChild()
            if sel == self._getTicketsButton: selName = 'GetTickets'
            elif sel == self._scrollWidget: selName = 'Scroll'
            elif sel == self._backButton: selName = 'Back'
            elif sel in self._tabButtons.values():
                selName = 'Tab:'+self._tabButtons.keys()[self._tabButtons.values().index(sel)]
            else: raise Exception("unrecognized selection")
            gWindowStates[self.__class__.__name__] = {'selName':selName,'tab':self._currentTab}
        except Exception:
            bs.printException('error saving state for',self.__class__)

    def _restoreState(self):
        try:
            try: selName = gWindowStates[self.__class__.__name__]['selName']
            except Exception: selName = None
            try: currentTab = bs.getConfig()['Store Tab']
            except Exception: currentTab = None
            if self._showTab is not None: currentTab = self._showTab
            if currentTab is None or currentTab not in self._tabButtons: currentTab = 'characters'
            if selName == 'GetTickets': sel = self._getTicketsButton
            elif selName == 'Back': sel = self._backButton
            elif selName == 'Scroll': sel = self._scrollWidget
            elif type(selName) is str and selName.startswith('Tab:'): sel = self._tabButtons[selName.split(':')[-1]]
            else: sel = self._tabButtons[currentTab]
            # if we were requested to show a tab, select it too..
            if self._showTab is not None and self._showTab in self._tabButtons:
                sel = self._tabButtons[self._showTab]
            self._setTab(currentTab)
            bs.containerWidget(edit=self._rootWidget,selectedChild=sel)
        except Exception:
            bs.printException('error restoring state for',self.__class__)

                
    def _onGetMoreTicketsPress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition='outLeft')
        window = GetTicketsWindow(fromModalStore=self._modal,storeBackLocation=self._backLocation).getRootWidget()
        if not self._modal:
            uiGlobals['mainMenuWindow'] = window

    def _back(self):
        self._saveState()
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        if not self._modal:
            if self._backLocation == 'CoopWindow':
                uiGlobals['mainMenuWindow'] = CoopWindow(transition='inLeft').getRootWidget()
            else:
                uiGlobals['mainMenuWindow'] = MainMenuWindow(transition='inLeft').getRootWidget()
        if self._onCloseCall is not None: self._onCloseCall()
    
def _handleLocalChatMessage(msg):
    global gPartyWindow
    if gPartyWindow is not None and gPartyWindow() is not None: gPartyWindow().onChatMessage(msg)

def _handleGainedTickets(count):
    bs.screenMessage(bs.getResource('getTicketsWindow.receivedTicketsText').replace('${COUNT}',str(count)),color=(0,1,0))
    bs.playSound(bs.getSound('cashRegister'))
    
gInviteConfirmWindows = []

def _handlePartyInvite(name,inviteID):
    import bsMainMenu
    bs.playSound(bs.getSound('fanfare'))
    
    # if we're not in the main menu, just print the invite
    # (don't want to screw up an in-progress game)
    inGame = not isinstance(bsInternal._getForegroundHostSession(),bsMainMenu.MainMenuSession)
    if inGame:
        bs.screenMessage((bs.getResource('gatherWindow.partyInviteText').replace('${NAME}',name)+'\n'
                          +bs.getResource('gatherWindow.partyInviteGooglePlayExtraText')),
                         color=(0.5,1,0))
    else:
        def doAccept(inviteID):
            bsInternal._acceptPartyInvitation(inviteID)
        c = ConfirmWindow(bs.getResource('gatherWindow.partyInviteText').replace('${NAME}',name),
                          bs.Call(doAccept,inviteID),width=500,height=150,
                          color=(0.75,1.0,0.0),
                          okText=bs.getResource('gatherWindow.partyInviteAcceptText'),
                          cancelText=bs.getResource('gatherWindow.partyInviteIgnoreText'))
        
        # lets store the invite-id away on the confirm window so we know if we need to kill it later
        c._partyInviteID = inviteID
        
        # store a weak-ref so we can get at this later
        global gInviteConfirmWindows
        gInviteConfirmWindows.append(weakref.ref(c))
        
        # go ahead and prune our weak refs while we're here.
        gInviteConfirmWindows = [w for w in gInviteConfirmWindows if w() is not None]

def _handlePartyInviteRevoke(inviteID):

    # if there's a confirm window up for joining this particular invite, kill it
    global gInviteConfirmWindows
    for ww in gInviteConfirmWindows:
        w = ww()
        if w is not None and w._partyInviteID == inviteID:
            bs.containerWidget(edit=w.getRootWidget(),transition='outRight')

class FileSelectorWindow(Window):

    def __init__(self,path,callback=None,showBasePath=True,validFileExtensions=[],allowFolders=False):
        self._width = 600
        self._height = 365 if gSmallUI else 418
        self._callback = callback
        self._basePath = path
        self._path = None
        self._recentPaths = []
        self._showBasePath = showBasePath
        self._validFileExtensions = ['.'+ext for ext in validFileExtensions]
        self._allowFolders = allowFolders
        
        self._scrollWidth = self._width-80
        self._scrollHeight = self._height-170
        self._R = bs.getResource('fileSelectorWindow')
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition='inRight',
                                              scale=2.23 if gSmallUI else 1.4 if gMedUI else 1.0,
                                              stackOffset=(0,-35) if gSmallUI else (0,0))
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-42),size=(0,0),
                          color=gTitleColor,hAlign="center",vAlign="center",
                          text=self._R.titleFolderText if (allowFolders and not validFileExtensions) else self._R.titleFileText if not allowFolders else self._R.titleFileFolderText,
                          maxWidth=210)

        
        self._buttonWidth = 146
        self._cancelButton = b = bs.buttonWidget(parent=self._rootWidget,position=(35,self._height-67),
                                                 autoSelect=True,size=(self._buttonWidth,50),label=bs.getResource('cancelText'),onActivateCall=self._cancel)
        bs.widget(edit=self._cancelButton,leftWidget=self._cancelButton)
        # self._selectButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width-buttonWidth - 30,self._height-63),
        #                                          size=(buttonWidth,60),label=bs.getResource('selectText'),onActivateCall=self._select)

        bColor = (0.6,0.53,0.63)

        self._backButton = bs.buttonWidget(parent=self._rootWidget,buttonType='square',position=(43,self._height-113),
                                           color=bColor,textColor=(0.75,0.7,0.8),enableSound=False,
                                           size=(55,35),label='Back' if False else bs.getSpecialChar('leftArrow'),onActivateCall=self._onBackPress)
                                         #size=(55,35),label='Back' if False else bs.getSpecialChar('leftArrow')"\xee\x80\x81",call=self._onBackPress)
                                         #size=(55,35),label='Up' if False else "\xc2\x81",call=self._onBackPress)

        # self._upButton = bs.buttonWidget(parent=self._rootWidget,buttonType='square',position=(39,self._height-113),
        #                                  color=bColor,textColor=(0.75,0.7,0.8),enableSound=False,
        #                                  size=(65,35),label='Up' if False else "\xc2\x82",onActivateCall=self._onUpPress)


        self._folderTex = bs.getTexture('folder')
        self._folderColor = (1.1,0.8,0.2)
        self._fileTex = bs.getTexture('file')
        self._fileColor = (1,1,1)
        self._useFolderButton = None

        self._folderCenter = self._width*0.5+15

        self._folderIcon = bs.imageWidget(parent=self._rootWidget,size=(40,40),position=(40,self._height-117),texture=self._folderTex,color=self._folderColor)
        self._pathText = bs.textWidget(parent=self._rootWidget,position=(self._folderCenter,self._height-98),size=(0,0),
                                       color=gTitleColor,hAlign="center",vAlign="center",text=self._path,maxWidth=self._width*0.9)

        # self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=((self._width-self._scrollWidth)*0.5,self._height-self._scrollHeight-119),
        #                                      size=(self._scrollWidth,self._scrollHeight))


        self._scrollWidget = None

        bs.containerWidget(edit=self._rootWidget,
                   #selectedChild=self._scrollWidget,
                   #startButton=self._selectButton,
                   cancelButton=self._cancelButton)

        self._setPath(path)

    def _onUpPress(self):
        self._onEntryActivated('..')

    def _onBackPress(self):
        if len(self._recentPaths) > 1:
            bs.playSound(bs.getSound('swish'))
            self._recentPaths.pop()
            self._setPath(self._recentPaths.pop())
        else:
            pass
            bs.playSound(bs.getSound('error'))
            #bs.screenMessage('can\'t go back further',color=(1,0,0))

    def _onFolderEntryActivated(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        if self._callback is not None:
            self._callback(self._path)
        
    def _onEntryActivated(self,entry):
        try:
            newPath = None
            if entry == '..':
                chunks = self._path.split('/')
                if len(chunks) > 1:
                    newPath = '/'.join(chunks[:-1])
                    if newPath == '': newPath = '/'
                else:
                    bs.playSound(bs.getSound('error'))
            else:
                if self._path == '/': testPath = self._path+entry
                else: testPath = self._path+'/'+entry
                if os.path.isdir(bs.utf8(testPath)):
                    bs.playSound(bs.getSound('swish'))
                    newPath = testPath
                elif os.path.isfile(bs.utf8(testPath)):
                    if self._isValidFilePath(testPath):
                        bs.playSound(bs.getSound('swish'))
                        bs.containerWidget(edit=self._rootWidget,transition='outRight')
                        if self._callback is not None:
                            self._callback(testPath)
                    else:
                        bs.playSound(bs.getSound('error'))
                else: print 'Error: FileSelectorWindow found non-file/dir:',testPath
        except Exception:
            bs.printException('error on FileSelectorWindow._onEntryActivated')

        if newPath is not None:
            self._setPath(newPath)

    class _RefreshThread(threading.Thread):
            
        def __init__(self,path,callback):
            threading.Thread.__init__(self)
            self._callback = callback
            self._path = path
        def run(self):
            try:
                startTime = time.time()
                files = [bs.uni(f) for f in os.listdir(bs.utf8(self._path))]
                duration = time.time()-startTime
                minTime = 0.1
                # make sure this takes at least 1/10 second so the user has time to see the selection highlight
                if duration < minTime: time.sleep(minTime-duration)
                bs.callInGameThread(bs.Call(self._callback,fileNames=files))
            except Exception,e:
                bs.printException()
                bs.callInGameThread(bs.Call(self._callback,error=str(e)))

    def _setPath(self,path,addToRecent=True):
        self._path = path
        if addToRecent: self._recentPaths.append(path)
        self._RefreshThread(path,self._refresh).start()
        
    def _refresh(self,fileNames=None,error=None):

        scrollWidgetSelected = (self._scrollWidget is None or self._rootWidget.getSelectedChild() == self._scrollWidget)

        inTopFolder = (self._path == self._basePath)
        hideTopFolder = inTopFolder and self._showBasePath is False

        if hideTopFolder: folderName = ''
        elif self._path == '/': folderName = '/'
        else: folderName = os.path.basename(self._path)

        bColor = (0.6,0.53,0.63)
        bColorDisabled = (0.65,0.65,0.65)

        if len(self._recentPaths) < 2:
            bs.buttonWidget(edit=self._backButton,color=bColorDisabled,textColor=(0.5,0.5,0.5))
        else:
            bs.buttonWidget(edit=self._backButton,color=bColor,textColor=(0.75,0.7,0.8))

        maxStrWidth = 300
        strWidth = min(maxStrWidth,bs.getStringWidth(folderName))
        bs.textWidget(edit=self._pathText,text=folderName,maxWidth=maxStrWidth)
        bs.imageWidget(edit=self._folderIcon,position=(self._folderCenter-strWidth*0.5-40,self._height-117),opacity=0.0 if hideTopFolder else 1.0)

        if self._scrollWidget is not None:
            self._scrollWidget.delete()

        if self._useFolderButton is not None:
            self._useFolderButton.delete()
            bs.widget(edit=self._cancelButton,rightWidget=self._backButton)

        self._scrollWidget = bs.scrollWidget(parent=self._rootWidget,position=((self._width-self._scrollWidth)*0.5,self._height-self._scrollHeight-119),
                                             size=(self._scrollWidth,self._scrollHeight))

        if scrollWidgetSelected:
            bs.containerWidget(edit=self._rootWidget,selectedChild=self._scrollWidget)

        # show error case..
        if error is not None:
            self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._scrollWidth,self._scrollHeight),background=False)
            bs.textWidget(parent=self._subContainer,color=(1,1,0,1),text=error,maxWidth=self._scrollWidth*0.9,
                          position=(self._scrollWidth*0.48,self._scrollHeight*0.57),size=(0,0),
                          hAlign='center',vAlign='center')

        else:
            fileNames = [f for f in fileNames if not f.startswith('.')]
            fileNames.sort(key=lambda x:x[0].lower())

            entries = fileNames
            entryHeight = 35

            folderEntryHeight = 100
            showFolderEntry = False

            showUseFolderButton = (self._allowFolders and not inTopFolder)

            self._subContainerHeight = entryHeight*len(entries) + (folderEntryHeight if showFolderEntry else 0)
            v = self._subContainerHeight - (folderEntryHeight if showFolderEntry else 0)

            self._subContainer = bs.containerWidget(parent=self._scrollWidget,size=(self._scrollWidth,self._subContainerHeight),background=False)

            bs.containerWidget(edit=self._scrollWidget,claimsLeftRight=False,claimsTab=False)
            bs.containerWidget(edit=self._subContainer,claimsLeftRight=False,claimsTab=False,
                               selectionLoops=False,printListExitInstructions=False)
            bs.widget(edit=self._subContainer,upWidget=self._backButton)

            if showUseFolderButton:
                self._useFolderButton = b = bs.buttonWidget(parent=self._rootWidget,position=(self._width - self._buttonWidth-35,self._height-67),
                                                            size=(self._buttonWidth,50),label=self._R.useThisFolderButtonText,
                                                            onActivateCall=self._onFolderEntryActivated)
                bs.widget(edit=b,leftWidget=self._cancelButton,downWidget=self._scrollWidget)
                bs.widget(edit=self._cancelButton,rightWidget=b)
                bs.containerWidget(edit=self._rootWidget,startButton=b)
                

            folderIconSize = 35
            for num,entry in enumerate(entries):
                c = bs.containerWidget(parent=self._subContainer,position=(0,v-entryHeight),
                                       size=(self._scrollWidth,entryHeight),rootSelectable=True,
                                       background=False,clickActivate=True,
                                       onActivateCall=bs.Call(self._onEntryActivated,entry))
                if num == 0:
                    bs.widget(edit=c,upWidget=self._backButton)
                isValidFilePath = self._isValidFilePath(entry)
                isDir = os.path.isdir(bs.utf8(self._path+'/'+entry))
                if isDir:
                    i = bs.imageWidget(parent=c,size=(folderIconSize,folderIconSize),position=(10,0.5*entryHeight-folderIconSize*0.5),
                                       drawController=c,texture=self._folderTex,color=self._folderColor)
                else:
                    i = bs.imageWidget(parent=c,size=(folderIconSize,folderIconSize),position=(10,0.5*entryHeight-folderIconSize*0.5),
                                       opacity=1.0 if isValidFilePath else 0.5,
                                       drawController=c,texture=self._fileTex,color=self._fileColor)
                t = bs.textWidget(parent=c,drawController=c,text=entry,hAlign='left',vAlign='center',
                                  position=(10+folderIconSize*1.05,entryHeight*0.5),
                                  size=(0,0),maxWidth=self._scrollWidth*0.93-50,color=(1,1,1,1) if (isValidFilePath or isDir) else (0.5,0.5,0.5,1))
                v -= entryHeight
                
    def _isValidFilePath(self,path):
        return any(path.lower().endswith(ext) for ext in self._validFileExtensions)
        
    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition='outRight')
        if self._callback is not None:
            self._callback(None)

def _doLegacyProUpgradeMessage(tickets):
    with bs.Context('UI'):
        ConfirmWindow(bs.getResource('store.freeBombSquadProText').replace('${COUNT}',str(tickets)),width=550,height=140,cancelButton=False)

gPowerRankingCache = {}
def _cachePowerRankingInfo(info):
    gPowerRankingCache['info'] = copy.deepcopy(info)

def _getCachedPowerRankingInfo():
    if 'info' in gPowerRankingCache:
        return gPowerRankingCache['info']
    else: return None

def _getPowerRankingPoints(data,subset=None):
    if data is None: return 0


    # if the data contains an achievement total, use that. otherwise calc locally
    if data['at'] is not None:
        totalAchValue = data['at']
    else:
        totalAchValue = 0
        for ach in bsAchievement.gAchievements:
            if ach.isComplete(): totalAchValue += ach.getPowerRankingValue()

    #return (data['a'] * data['am']

    trophiesTotal = (data['t0a'] * data['t0am']
                     + data['t0b'] * data['t0bm']
                     + data['t1'] * data['t1m']
                     + data['t2'] * data['t2m']
                     + data['t3'] * data['t3m']
                     + data['t4'] * data['t4m'])
    if subset == 'trophyCount':
        return data['t0a']+data['t0b']+data['t1']+data['t2']+data['t3']+data['t4']
    elif subset == 'trophies': return trophiesTotal
    elif subset is not None: raise Exception("invalid subset value: "+str(subset))

    #if bsUtils._havePro(): proMult = 1.0 + float(bsInternal._getAccountMiscReadVal('proPowerRankingBoost',0.0))*0.01
    if data['p']: proMult = 1.0 + float(bsInternal._getAccountMiscReadVal('proPowerRankingBoost',0.0))*0.01
    else: proMult = 1.0

    # for final value, apply our pro mult and activeness-mult
    return int((totalAchValue+trophiesTotal) * (data['act'] if data['act'] is not None else 1.0) * proMult)

# cached info about individual tourneys
gTournamentInfo = {}
# the cached list of tourneys/challenges for our account
gAccountTournamentList = None
gAccountChallengeList = None

def _getCachedChallenge(challengeID):
    if gAccountChallengeList is None: return None
    if gAccountChallengeList['accountState'] != bsInternal._getAccountStateNum(): return None
    for c in gAccountChallengeList['challenges']:
        if c['challengeID'] == challengeID:
            return c
    return None

def _cacheTournamentInfo(info):
    for entry in info:
        cacheEntry = gTournamentInfo[entry['tournamentID']] = copy.deepcopy(entry)
        # also store the time we received this, so we can adjust time-remaining values/etc
        cacheEntry['timeReceived'] = bs.getRealTime()
        cacheEntry['valid'] = True
    
def showSignInPrompt(accountType=None):

    if accountType == 'Google Play':
        ConfirmWindow(bs.getResource('notSignedInGooglePlayErrorText'),
                      lambda: bsInternal._signIn('Google Play'),
                      okText=bs.getResource('accountSettingsWindow.signInText'),width=460,height=130)
    else:
        ConfirmWindow(bs.getResource('notSignedInErrorText'),
                      bs.Call(AccountWindow,modal=True,closeOnceSignedIn=True),
                      okText=bs.getResource('accountSettingsWindow.signInText'),width=460,height=130)

def showGetTicketsPrompt():
    ConfirmWindow(bs.translate('serverResponses','You don\'t have enough tickets for this!'),
                  bs.Call(GetTicketsWindow,modal=True),
                  okText=bs.getResource('getTicketsWindow.titleText'),width=460,height=130)

class PowerRankingButton(object):
    
    def __init__(self,parent,position,size,scale,onActivateCall=None,transitionDelay=None,color=None,textColor=None,smoothUpdateDelay=None):
        if onActivateCall is None: onActivateCall = bs.WeakCall(self._defaultOnActivateCall)
        self._onActivateCall = onActivateCall

        if smoothUpdateDelay is None: smoothUpdateDelay = 1000
        self._smoothUpdateDelay = smoothUpdateDelay
        
        self._size = size
        self._scale = scale

        if color is None: color = (0.5,0.6,0.5)
        if textColor is None: textColor = (1,1,1)

        self._color = color
        self._textColor = textColor
        self._headerColor = (0.8,0.8,2.0)
        self._parent = parent
        self._button = bs.buttonWidget(parent=parent,size=size,label='',buttonType='square',
                                       scale=scale,autoSelect=True,onActivateCall=self._onActivate,transitionDelay=transitionDelay,color=color)

        self._titleText = bs.textWidget(parent=parent,size=(0,0),drawController=self._button,
                                        hAlign='center',vAlign='center',maxWidth=size[0]*scale*0.85,text=bs.getResource('league.leagueRankText',fallback='coopSelectWindow.powerRankingText'),
                                        color=self._headerColor,flatness=1.0,shadow=1.0,scale=scale*0.5,transitionDelay=transitionDelay)
        
        self._valueText = bs.textWidget(parent=parent,size=(0,0),
                                        hAlign='center',vAlign='center',maxWidth=size[0]*scale*0.85,text='-',
                                        drawController=self._button,big=True,
                                        scale=scale,transitionDelay=transitionDelay,color=textColor)

        self._smoothPercent = None
        self._percent = None
        self._smoothRank = None
        self._rank = None
        self._tickingNode = None
        self._smoothIncreaseSpeed = 1.0
        self._league = None
        
        # take note of our account state; we'll refresh later if this changes
        self._accountStateNum = bsInternal._getAccountStateNum()
        self._lastPowerRankingQueryTime = None
        self._doingPowerRankingQuery = False
        
        self.setPosition(position)

        self._bgFlash = False
        
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),timeType='real',repeat=True)
        self._update()

        # if we've got cached power-ranking data already, apply it..
        info = _getCachedPowerRankingInfo()
        if info is not None:
            self._updateForPowerRankingInfo(info)

    def _onActivate(self):
        bsInternal._incrementAnalyticsCount('League rank button press')
        self._onActivateCall()
        
    def __del__(self):
        if self._tickingNode is not None:
            self._tickingNode.delete()

    def _startSmoothUpdate(self):
        self._smoothUpdateTimer = bs.Timer(50,bs.WeakCall(self._smoothUpdate),repeat=True,timeType='real')
        
    def _smoothUpdate(self):
        try:

            if not self._button.exists(): return
            
            if self._tickingNode is None:
                with bs.Context('UI'):
                    self._tickingNode = bs.newNode('sound',attrs={'sound':bs.getSound('scoreIncrease'),'positional':False})

            # if self._rank is None and self._percent is None:
            #     print 'fixme; have neither rank nor percent in _smoothUpdate'
                
            #if self._rank is not None or :
            self._bgFlash = (not self._bgFlash)
            colorUsed = (self._color[0]*2,self._color[1]*2,self._color[2]*2) if self._bgFlash else self._color
            textColorUsed = (1,1,1) if self._bgFlash else self._textColor
            headerColorUsed = (1,1,1) if self._bgFlash else self._headerColor

            if self._rank is not None:
                self._smoothRank -= 1.0 * self._smoothIncreaseSpeed
                finished = (int(self._smoothRank) <= self._rank)
            elif self._smoothPercent is not None:
                self._smoothPercent += 1.0 * self._smoothIncreaseSpeed
                finished = (int(self._smoothPercent) >= self._percent)
            else:
                finished = True
            if finished:
                if self._rank is not None: self._smoothRank = float(self._rank)
                elif self._percent is not None: self._smoothPercent = float(self._percent)
                #self._smoothRank = float(self._rank)
                colorUsed = self._color
                textColorUsed = self._textColor
                self._smoothUpdateTimer = None
                if self._tickingNode is not None:
                    self._tickingNode.delete()
                    self._tickingNode = None
                bs.playSound(bs.getSound('cashRegister2'))
                diffText = bs.textWidget(parent=self._parent,size=(0,0),
                                         hAlign='center',vAlign='center',text='+'+self._improvementText+"!",
                                         position=(self._position[0]+self._size[0]*0.5*self._scale,self._position[1]+self._size[1]*-0.2*self._scale),
                                         color=(0,1,0),flatness=1.0,shadow=0.0,scale=self._scale*0.7)
                def safeDelete(widget):
                    if widget.exists():
                        widget.delete()
                bs.realTimer(2000,bs.Call(safeDelete,diffText))
            if self._rank is not None:
                numText = bs.getResource('numberText')
                statusText = numText.replace('${NUMBER}',str(int(self._smoothRank)))
            elif self._smoothPercent is not None:
                statusText = str(int(self._smoothPercent))+'%'
            else:
                statusText = '-'
            bs.textWidget(edit=self._valueText,text=statusText,color=textColorUsed)
            bs.textWidget(edit=self._titleText,color=headerColorUsed)

            bs.buttonWidget(edit=self._button,color=colorUsed)

        except Exception:
            bs.printException('error doing smooth update')
            self._smoothUpdateTimer = None
            
    def _updateForPowerRankingInfo(self,data):

        # if our button has died, ignore..
        if not self._button.exists(): return

        inTop = True if (data is not None and data['rank'] is not None) else False
        numText = bs.getResource('numberText')
        doPercent = False
        if data is None or bsInternal._getAccountState() != 'SIGNED_IN':
            self._percent = self._rank = None
            statusText = '-'
        elif inTop:
            self._percent = None
            self._rank = data['rank']

            prevLeague = self._league
            self._league = data['l']

            # if this is the first set, league has changed, or rank has gotten worse, snap the smooth value immediately
            if self._smoothRank is None or prevLeague != self._league or self._rank > int(self._smoothRank):
                self._smoothRank = float(self._rank)
            statusText = numText.replace('${NUMBER}',str(int(self._smoothRank)))

            # TEST INCREASE FUNCTIONALITY
            # print 'RUNNING INCREASE TEST'
            # self._rank -= random.randrange(40)
        else:
            try:
                if not data['scores'] or data['scores'][-1][1] <= 0:
                    self._percent = self._rank = None
                    statusText = '-'
                else:
                    ourPoints = _getPowerRankingPoints(data)
                    progress = float(ourPoints)/data['scores'][-1][1]
                    self._percent = int(progress*100.0)
                    self._rank = None
                    doPercent = True

                    prevLeague = self._league
                    self._league = data['l']


                    # if this is the first set, league has changed, or percent has decreased, snap the smooth value immediately
                    if self._smoothPercent is None or prevLeague != self._league or self._percent < int(self._smoothPercent):
                        self._smoothPercent = float(self._percent)
                    statusText = str(int(self._smoothPercent))+'%'

                    # print 'RUNNING INCREASE TEST'
                    # self._percent += random.randrange(40)
                
            except Exception:
                bs.printException('error updating power ranking')
                self._percent = self._rank = None
                statusText = '-'
                
        # if we're doing a smooth update ,set a timer..
        if self._rank is not None and int(self._smoothRank) != self._rank:
            self._improvementText = str(-(int(self._rank)-int(self._smoothRank)))
            diff = abs(self._rank - self._smoothRank)
            if diff > 100:
                self._smoothIncreaseSpeed = diff/80.0
            elif diff > 50:
                self._smoothIncreaseSpeed = diff/70.0
            elif diff > 25:
                self._smoothIncreaseSpeed = diff/55.0
            else:
                self._smoothIncreaseSpeed = diff/40.0
            self._smoothIncreaseSpeed = max(0.4,self._smoothIncreaseSpeed)
            bs.realTimer(self._smoothUpdateDelay,bs.WeakCall(self._startSmoothUpdate))
            
        if self._percent is not None and int(self._smoothPercent) != self._percent:
            self._improvementText = str((int(self._percent)-int(self._smoothPercent)))
            diff = abs(self._percent - self._smoothPercent)
            self._smoothIncreaseSpeed = 0.3
            bs.realTimer(self._smoothUpdateDelay,bs.WeakCall(self._startSmoothUpdate))

        if doPercent:
            bs.textWidget(edit=self._titleText,text=bs.getResource('coopSelectWindow.toRankedText'))
        else:
            try:
                t = bs.getResource('league.leagueFullText').replace('${NAME}',bs.translate('leagueNames',data['l']['n']))
                tColor = data['l']['c']
            except Exception:
                t = bs.getResource('league.leagueRankText',fallback='coopSelectWindow.powerRankingText')
                tColor = gTitleColor
            #bs.textWidget(edit=self._titleText,text=bs.getResource('league.leagueRankText',fallback='coopSelectWindow.powerRankingText'))
            bs.textWidget(edit=self._titleText,text=t,color=tColor)
        bs.textWidget(edit=self._valueText,text=statusText)
        
    def _onPowerRankingQueryResponse(self,data):
        self._doingPowerRankingQuery = False
        _cachePowerRankingInfo(data)
        # if data is not None:
        #     data['rank'] -= 10
        self._updateForPowerRankingInfo(data)

    def _update(self):
        curTime = bs.getRealTime()

        # if our account state has changed, refresh our UI
        accountStateNum = bsInternal._getAccountStateNum()
        if accountStateNum != self._accountStateNum:
            self._accountStateNum = accountStateNum
            #self._refresh()
            # and power ranking too...
            if not self._doingPowerRankingQuery: self._lastPowerRankingQueryTime = None

        # send off a new power-ranking query if its been long enough or whatnot..
        if not self._doingPowerRankingQuery and (self._lastPowerRankingQueryTime is None or curTime-self._lastPowerRankingQueryTime > 30000):
            self._lastPowerRankingQueryTime = curTime
            self._doingPowerRankingQuery = True
            bsInternal._powerRankingQuery(callback=bs.WeakCall(self._onPowerRankingQueryResponse))
        
    def _defaultOnActivateCall(self):
        PowerRankingWindow(modal=True,originWidget=self._button)

    def setPosition(self, position):
        self._position = position
        if not self._button.exists():
            return
        bs.buttonWidget(edit=self._button,position=self._position)
        bs.textWidget(edit=self._titleText,position=(self._position[0]+self._size[0]*0.5*self._scale,self._position[1]+self._size[1]*0.82*self._scale))
        bs.textWidget(edit=self._valueText,position=(self._position[0]+self._size[0]*0.5*self._scale,self._position[1]+self._size[1]*0.36*self._scale))
        
    def getButtonWidget(self):
        return self._button
        
class StoreButton(object):

    def __init__(self,parent,position,size,scale,onActivateCall=None,transitionDelay=None,color=None,
                 textColor=None,showTickets=False,buttonType=None,saleScale=1.0):
        self._position = position
        self._size = size
        self._scale = scale
        
        if onActivateCall is None: onActivateCall = bs.WeakCall(self._defaultOnActivateCall)
        self._onActivateCall = onActivateCall
        
        self._button = bs.buttonWidget(parent=parent,size=size,label='' if showTickets else bs.getResource('storeText'),scale=scale,
                                       autoSelect=True,onActivateCall=self._onActivate,transitionDelay=transitionDelay,
                                       color=color,buttonType=buttonType)

        if showTickets:
            self._titleText = bs.textWidget(parent=parent,position=(position[0]+size[0]*0.5*scale,position[1]+size[1]*0.65*scale),size=(0,0),
                                            hAlign='center',vAlign='center',maxWidth=size[0]*scale*0.65,text=bs.getResource('storeText'),
                                            drawController=self._button,
                                            scale=scale,transitionDelay=transitionDelay,color=textColor)
            self._ticketText = bs.textWidget(parent=parent,size=(0,0),
                                             hAlign='center',vAlign='center',maxWidth=size[0]*scale*0.85,text='',
                                             color=(1,0.5,0),flatness=1.0,shadow=0.0,scale=scale*0.6,transitionDelay=transitionDelay)
        else:
            self._titleText = None
            self._ticketText = None

        self._circleRad = 12*scale
        self._availablePurchaseBacking = bs.imageWidget(parent=parent,color=(1,0,0),
                                                        drawController=self._button,
                                                        size=(2.2*self._circleRad,2.2*self._circleRad),
                                                        texture=bs.getTexture('circleShadow'),transitionDelay=transitionDelay)
        self._availablePurchaseText = bs.textWidget(parent=parent,size=(0,0),
                                                    hAlign='center',vAlign='center',text='',
                                                    drawController=self._button,
                                                    color=(1,1,1),flatness=1.0,shadow=1.0,scale=0.6*scale,
                                                    maxWidth=self._circleRad*1.4,
                                                    transitionDelay=transitionDelay)

        self._saleCircleRad = 18*scale*saleScale
        self._saleBacking = bs.imageWidget(parent=parent,color=(0.5,0,1.0),
                                           drawController=self._button,
                                           size=(2*self._saleCircleRad,2*self._saleCircleRad),
                                           texture=bs.getTexture('circleZigZag'),transitionDelay=transitionDelay)
        self._saleTitleText = bs.textWidget(parent=parent,size=(0,0),
                                       hAlign='center',vAlign='center',
                                       drawController=self._button,
                                       color=(0,1,0),flatness=1.0,shadow=0.0,scale=0.5*scale*saleScale,
                                       maxWidth=self._saleCircleRad*1.5,transitionDelay=transitionDelay)
        self._saleTimeText = bs.textWidget(parent=parent,size=(0,0),
                                       hAlign='center',vAlign='center',
                                       drawController=self._button,
                                       color=(0,1,0),flatness=1.0,shadow=0.0,scale=0.4*scale*saleScale,
                                       maxWidth=self._saleCircleRad*1.5,transitionDelay=transitionDelay)
        
        self.setPosition(position)
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),repeat=True,timeType='real')
        self._update()

    def _onActivate(self):
        bsInternal._incrementAnalyticsCount('Store button press')
        self._onActivateCall()
        
        
    def setPosition(self,position):
        self._position = position
        self._circleCenter = (position[0]+0.1*self._size[0]*self._scale,position[1]+self._size[1]*self._scale*0.8)
        self._saleCircleCenter = (position[0]+0.07*self._size[0]*self._scale,position[1]+self._size[1]*self._scale*0.8)

        if not self._button.exists():
            return
        bs.buttonWidget(edit=self._button,position=self._position)
        if self._titleText is not None:
            bs.textWidget(edit=self._titleText,position=(self._position[0]+self._size[0]*0.5*self._scale,self._position[1]+self._size[1]*0.65*self._scale))
        if self._ticketText is not None:
            bs.textWidget(edit=self._ticketText,position=(position[0]+self._size[0]*0.5*self._scale,position[1]+self._size[1]*0.28*self._scale),size=(0,0))
        bs.imageWidget(edit=self._availablePurchaseBacking,
                       position=(self._circleCenter[0]-self._circleRad*1.02,self._circleCenter[1]-self._circleRad*1.13))
        bs.textWidget(edit=self._availablePurchaseText,position=self._circleCenter)

        bs.imageWidget(edit=self._saleBacking,
                       position=(self._saleCircleCenter[0]-self._saleCircleRad,self._saleCircleCenter[1]-self._saleCircleRad))
        bs.textWidget(edit=self._saleTitleText,position=(self._saleCircleCenter[0],self._saleCircleCenter[1]+self._saleCircleRad*0.3))
        bs.textWidget(edit=self._saleTimeText,position=(self._saleCircleCenter[0],self._saleCircleCenter[1]-self._saleCircleRad*0.3))
        
    
    def _defaultOnActivateCall(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            showSignInPrompt()
            return
        StoreWindow(modal=True,originWidget=self._button)
        
    def getButtonWidget(self):
        return self._button

    def _update(self):
        if not self._button.exists(): return # our instance may outlive our UI objects..
        
        #print 'UPDATING STORE BUTTON'
        if self._ticketText is not None:
            if bsInternal._getAccountState() == 'SIGNED_IN':
                s = bs.getSpecialChar('ticket')+str(bsInternal._getAccountTicketCount())
            else: s = '-'
            bs.textWidget(edit=self._ticketText,text=s)
        availablePurchases = _getAvailablePurchaseCount()

        # old pro sale stuff..
        saleTime = _getAvailableSaleTime('extras')

        #..also look for new style sales
        if saleTime is None:
            import datetime
            salesRaw = bsInternal._getAccountMiscReadVal('sales',{})
            saleTimes = []
            try:
                # look at the current set of sales; filter any with time remaining that we don't own
                for saleItem, saleInfo in salesRaw.items():
                    if not bsInternal._getPurchased(saleItem):
                        toEnd = (datetime.datetime.utcfromtimestamp(saleInfo['e']) - datetime.datetime.utcnow()).total_seconds()
                        if toEnd > 0:
                            saleTimes.append(toEnd)
            except Exception:
                bs.printException("Error parsing sales")
            if saleTimes:
                saleTime = int(min(saleTimes)*1000)
        
        if saleTime is not None:
            bs.textWidget(edit=self._saleTitleText,text=bs.getResource('store.saleText'))
            bs.textWidget(edit=self._saleTimeText,text=bsUtils.getTimeString(saleTime,centi=False))
            bs.imageWidget(edit=self._saleBacking,opacity=1.0)
            bs.imageWidget(edit=self._availablePurchaseBacking,opacity=1.0)
            bs.textWidget(edit=self._availablePurchaseText,text='')
            bs.imageWidget(edit=self._availablePurchaseBacking,opacity=0.0)
        else:
            bs.imageWidget(edit=self._saleBacking,opacity=0.0)
            bs.textWidget(edit=self._saleTimeText,text='')
            bs.textWidget(edit=self._saleTitleText,text='')
            if availablePurchases > 0:
                bs.textWidget(edit=self._availablePurchaseText,text=str(availablePurchases))
                bs.imageWidget(edit=self._availablePurchaseBacking,opacity=1.0)
            else:
                bs.textWidget(edit=self._availablePurchaseText,text='')
                bs.imageWidget(edit=self._availablePurchaseBacking,opacity=0.0)

    # def __del__(self):
    #     print '~StoreButton()'

_gStoreLayout = None
_gStoreItems = None

def _getStoreItem(item):
    return _getStoreItems()[item]

# given an item-info as returned from _getStoreItem, returns a translated name
def _getStoreItemNameTranslated(itemName):
    itemInfo = _getStoreItem(itemName)
    if itemName.startswith('characters.'):
        return bs.translate('characterNames',itemInfo['character'])
    elif itemName in ['upgrades.pro','pro']:
        return bs.getResource('store.bombSquadProNameText').replace('${APP_NAME}',bs.getResource('titleText'))
    elif itemName.startswith('maps.'):
        mapType = itemInfo['mapType']
        return bsMap.getLocalizedMapName(mapType.name)
    elif itemName.startswith('games.'):
        gameType = itemInfo['gameType']
        return gameType.getNameLocalized()
    elif itemName.startswith('icons.'):
        return bs.getResource('editProfileWindow.iconText')
    else: raise Exception('unrecognized item: '+itemName)
    

def _instantiateStoreItemDisplay(itemName,item,parentWidget,bPos,bWidth,bHeight,buttonOffsetH=0,bOffsH2=0,bOffsV2=0,delay=0,button=True):
    itemInfo = _getStoreItem(itemName)
    title = 'untitled'
    titleV = 0.24
    priceV = 0.145
    baseTextScale = 1.0

    item['name'] = title = _getStoreItemNameTranslated(itemName)

    if button:
        item['button'] = b = bs.buttonWidget(parent=parentWidget,position=bPos,
                                             transitionDelay=delay,
                                             showBufferTop=76.0,
                                             enableSound=False,
                                             buttonType='square',
                                             size=(bWidth,bHeight),
                                             autoSelect=True,
                                             label='')
        bs.widget(edit=b,showBufferBottom=76.0)
    else: b = None
    
    bOffsX = -0.015*bWidth
    checkPos = 0.76

    if itemName.startswith('characters.'):
        character = bsSpaz.appearances[itemInfo['character']]
        tintColor=(itemInfo['color'] if 'color' in itemInfo
                   else character.defaultColor if character.defaultColor is not None
                   else (1,1,1))
        tint2Color=(itemInfo['highlight'] if 'highlight' in itemInfo
                    else character.defaultHighlight if character.defaultHighlight is not None
                    else (1,1,1))
        iconTex=character.iconTexture
        tintTex = character.iconMaskTexture
        titleV = 0.255
        priceV = 0.145
    elif itemName in ['upgrades.pro','pro']:
        baseTextScale = 0.6
        titleV = 0.82
        priceV = 0.17
    elif itemName.startswith('maps.'):
        mapType = itemInfo['mapType']
        texName = mapType.getPreviewTextureName()
        titleV = 0.312
        priceV = 0.17

    elif itemName.startswith('games.'):
        gameType = itemInfo['gameType']
        modes = []
        if gameType.supportsSessionType(bs.CoopSession): modes.append(bs.getResource('playModes.coopText'))
        if gameType.supportsSessionType(bs.TeamsSession): modes.append(bs.getResource('playModes.teamsText'))
        if gameType.supportsSessionType(bs.FreeForAllSession): modes.append(bs.getResource('playModes.freeForAllText'))
        modes = ', '.join(modes)
        desc = gameType.getDescriptionLocalized(bs.CoopSession)
        texName = itemInfo['previewTex']
        baseTextScale = 0.8
        titleV = 0.48
        priceV = 0.17
        
    elif itemName.startswith('icons.'):
        baseTextScale = 1.5
        priceV = 0.2
        checkPos = 0.6


    if itemName.startswith('characters.'):
        frameSize = bWidth*0.7
        insetTex = bs.getTexture('frameInset')
        insetModel = bs.getModel('frameInset')
        imDim = frameSize*(100.0/113.0)
        imPos = (bPos[0]+bWidth*0.5-imDim*0.5+bOffsX,bPos[1]+bHeight*0.57-imDim*0.5)
        framePos = (bPos[0]+bWidth*0.5-frameSize*0.5+bOffsX,bPos[1]+bHeight*0.57-frameSize*0.5)
        maskTexture=bs.getTexture('characterIconMask')
        bs.imageWidget(parent=parentWidget,position=imPos,size=(imDim,imDim),color=(1,1,1),
                       transitionDelay=delay,
                       maskTexture=maskTexture,
                       drawController=b,
                       texture=bs.getTexture(iconTex),
                       tintTexture=bs.getTexture(tintTex),
                       tintColor=tintColor,tint2Color=tint2Color)

    if itemName in ['pro','upgrades.pro']:
        frameSize = bWidth*0.5
        imDim = frameSize*(100.0/113.0)
        imPos = (bPos[0]+bWidth*0.5-imDim*0.5+bOffsX,bPos[1]+bHeight*0.5-imDim*0.5)
        bs.imageWidget(parent=parentWidget,position=imPos,size=(imDim,imDim),
                       transitionDelay=delay,
                       drawController=b,
                       color=(0.3,0.0,0.3),opacity=0.3,
                       texture=bs.getTexture('logo'))
        t = (bs.getResource('store.bombSquadProDescriptionText')
             .replace('${FREE_PLAYER_LIMIT}','3')
             .replace('${MAX_PLAYERS}','8')
             .replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('proBonusTickets',100)))
             .replace('${PERCENT}',str(bsInternal._getAccountMiscReadVal('proPowerRankingBoost',5)))
             .replace('${INF_ONSLAUGHT}',bs.translate('coopLevelNames','Infinite Onslaught'))
             .replace('${INF_RUNAROUND}',bs.translate('coopLevelNames','Infinite Runaround')))

        item['descriptionText'] = bs.textWidget(parent=parentWidget,text=t,position=(bPos[0]+bWidth*0.5,bPos[1]+bHeight*0.485),
                                                transitionDelay=delay,scale=bWidth*(1.0/230.0)*baseTextScale*0.75,
                                                maxWidth=bWidth*0.75,maxHeight=bHeight*0.53,size=(0,0),hAlign='center',vAlign='center',
                                                drawController=b,
                                                color=(0.3,1,0.3))

    if itemName.startswith('icons.'):
        item['iconText'] = bs.textWidget(parent=parentWidget,text=itemInfo['icon'],position=(bPos[0]+bWidth*0.5,bPos[1]+bHeight*0.5),
                                         transitionDelay=delay,scale=bWidth*(1.0/230.0)*baseTextScale*2.0,
                                         maxWidth=bWidth*0.9,maxHeight=bHeight*0.9,size=(0,0),hAlign='center',vAlign='center',
                                         drawController=b)
        
    if itemName.startswith('maps.'):
        frameSize = bWidth*0.9
        imDim = frameSize*(100.0/113.0)
        #imPos = (bPos[0]+bWidth*0.5-imDim*0.5+bOffsX,bPos[1]+bHeight*0.43-imDim*0.25)
        imPos = (bPos[0]+bWidth*0.5-imDim*0.5+bOffsX,bPos[1]+bHeight*0.62-imDim*0.25)
        modelOpaque = bs.getModel('levelSelectButtonOpaque')
        modelTransparent = bs.getModel('levelSelectButtonTransparent')
        maskTex = bs.getTexture('mapPreviewMask')
        bs.imageWidget(parent=parentWidget,position=imPos,size=(imDim,imDim*0.5),
                       transitionDelay=delay,
                       modelOpaque=modelOpaque,
                       modelTransparent=modelTransparent,
                       maskTexture=maskTex,
                       drawController=b,
                       texture=bs.getTexture(texName))

    if itemName.startswith('games.'):
        frameSize = bWidth*0.8
        imDim = frameSize*(100.0/113.0)
        #imPos = (bPos[0]+bWidth*0.5-imDim*0.5+bOffsX,bPos[1]+bHeight*0.43-imDim*0.25)
        imPos = (bPos[0]+bWidth*0.5-imDim*0.5+bOffsX,bPos[1]+bHeight*0.72-imDim*0.25)
        modelOpaque = bs.getModel('levelSelectButtonOpaque')
        modelTransparent = bs.getModel('levelSelectButtonTransparent')
        maskTex = bs.getTexture('mapPreviewMask')
        bs.imageWidget(parent=parentWidget,position=imPos,size=(imDim,imDim*0.5),
                       transitionDelay=delay,
                       modelOpaque=modelOpaque,
                       modelTransparent=modelTransparent,
                       maskTexture=maskTex,
                       drawController=b,
                       texture=bs.getTexture(texName))
        #desc = 'testing\ntriple\nlines and stuff'
        item['descriptionText'] = bs.textWidget(parent=parentWidget,text=desc,position=(bPos[0]+bWidth*0.5,bPos[1]+bHeight*0.36),
                                                transitionDelay=delay,scale=bWidth*(1.0/230.0)*baseTextScale*0.78,
                                                maxWidth=bWidth*0.8,maxHeight=bHeight*0.14,size=(0,0),hAlign='center',vAlign='center',
                                                drawController=b,flatness=1.0,shadow=0.0,
                                                color=(0.6,1,0.6))
        item['gameModesText'] = bs.textWidget(parent=parentWidget,text=modes,position=(bPos[0]+bWidth*0.5,bPos[1]+bHeight*0.26),
                                              transitionDelay=delay,scale=bWidth*(1.0/230.0)*baseTextScale*0.65,
                                              maxWidth=bWidth*0.8,size=(0,0),hAlign='center',vAlign='center',
                                              drawController=b,shadow=0,flatness=1.0,
                                              color=(0.6,0.8,0.6))

    if not itemName.startswith('icons.'):
        item['titleText'] = bs.textWidget(parent=parentWidget,text=title,position=(bPos[0]+bWidth*0.5+bOffsX,bPos[1]+bHeight*titleV),
                                          transitionDelay=delay,scale=bWidth*(1.0/230.0)*baseTextScale,
                                          maxWidth=bWidth*0.8,size=(0,0),hAlign='center',vAlign='center',
                                          drawController=b,
                                          color=(0.7,0.9,0.7,1.0))
                                          #color=(1,0,0,1))
        
    item['purchaseCheck'] = bs.imageWidget(parent=parentWidget,
                                           position=(bPos[0]+bWidth*checkPos,bPos[1]+bHeight*0.05),
                                           transitionDelay=delay,
                                           modelTransparent=bs.getModel('checkTransparent'),
                                           opacity=0.0,
                                           size=(60,60),
                                           #color=(0.6,1.0,0.6),
                                           color=(0.6,0.5,0.8),
                                           drawController=b,texture=bs.getTexture('uiAtlas'))
    item['priceWidget'] = bs.textWidget(parent=parentWidget,text='',position=(bPos[0]+bWidth*0.5+bOffsX,bPos[1]+bHeight*priceV),
                                        transitionDelay=delay,scale=bWidth*(1.0/300.0)*baseTextScale,
                                        maxWidth=bWidth*0.9,size=(0,0),hAlign='center',vAlign='center',
                                        drawController=b,
                                        color=(1,0.5,0.0,1.0))
    item['priceWidgetLeft'] = bs.textWidget(parent=parentWidget,text='',position=(bPos[0]+bWidth*0.33+bOffsX,bPos[1]+bHeight*priceV),
                                            transitionDelay=delay,scale=bWidth*(1.0/300.0)*baseTextScale,
                                            maxWidth=bWidth*0.3,size=(0,0),hAlign='center',vAlign='center',
                                            drawController=b,
                                            color=(1,0.5,0.0,0.5))
    item['priceWidgetRight'] = bs.textWidget(parent=parentWidget,text='',position=(bPos[0]+bWidth*0.66+bOffsX,bPos[1]+bHeight*priceV),
                                             transitionDelay=delay,scale=1.1*bWidth*(1.0/300.0)*baseTextScale,
                                             maxWidth=bWidth*0.3,size=(0,0),hAlign='center',vAlign='center',
                                             drawController=b,
                                             color=(1,0.5,0.0,1.0))
    item['priceSlashWidget'] = bs.imageWidget(parent=parentWidget,position=(bPos[0]+bWidth*0.33+bOffsX-36,bPos[1]+bHeight*priceV-35),
                                              transitionDelay=delay,texture=bs.getTexture('slash'),
                                              opacity=0.0,
                                              size=(70,70),drawController=b,color=(1,0,0))
    badgeRad = 44
    badgeCenter = (bPos[0]+bWidth*0.1+bOffsX,bPos[1]+bHeight*0.87)
    item['saleBGWidget'] = bs.imageWidget(parent=parentWidget,position=(badgeCenter[0]-badgeRad,badgeCenter[1]-badgeRad),
                                          opacity=0.0,
                                          transitionDelay=delay,texture=bs.getTexture('circleZigZag'),drawController=b,
                                          size=(badgeRad*2,badgeRad*2),color=(0.5,0,1))
    item['saleTitleWidget'] = bs.textWidget(parent=parentWidget,position=(badgeCenter[0],badgeCenter[1]+12),
                                            transitionDelay=delay,scale=1.0,
                                            maxWidth=badgeRad*1.6,size=(0,0),hAlign='center',vAlign='center',
                                            drawController=b,shadow=0.0,flatness=1.0,
                                            color=(0,1,0))
    item['saleTimeWidget'] = bs.textWidget(parent=parentWidget,position=(badgeCenter[0],badgeCenter[1]-12),
                                           transitionDelay=delay,scale=0.7,
                                           maxWidth=badgeRad*1.6,size=(0,0),hAlign='center',vAlign='center',
                                           drawController=b,shadow=0.0,flatness=1.0,
                                           color=(0.0,1,0.0,1))
    
def _getStoreItemDisplaySize(itemName):
    if itemName.startswith('characters.'): return (340*0.6,430*0.6)
    elif itemName in ['pro','upgrades.pro']: return (650*0.9,500*0.75)
    elif itemName.startswith('maps.'): return (510*0.6,450*0.6)
    elif itemName.startswith('icons.'): return (265*0.6,250*0.6)
    else: return (450*0.6,450*0.6)

# returns pertinant info about all purchasable items (whether or not they appear in the store)
def _getStoreItems():
    global _gStoreItems
    if _gStoreItems is None:
        import bsNinjaFight
        import bsMeteorShower
        import bsTargetPractice
        import bsEasterEggHunt

        _gStoreItems = {
            'characters.kronk':{'character':'Kronk'},
            'characters.zoe':{'character':'Zoe'},
            'characters.jackmorgan':{'character':'Jack Morgan'},
            'characters.mel':{'character':'Mel'},
            'characters.snakeshadow':{'character':'Snake Shadow'},
            'characters.bones':{'character':'Bones'},
            'characters.bernard':{'character':'Bernard','highlight':(0.6,0.5,0.8)},
            'characters.pixie':{'character':'Pixel'},
            'characters.frosty':{'character':'Frosty'},
            'characters.pascal':{'character':'Pascal'},
            'characters.cyborg':{'character':'B-9000'},
            'characters.agent':{'character':'Agent Johnson'},
            'characters.taobaomascot':{'character':'Taobao Mascot'},
            'characters.santa':{'character':'Santa Claus'},
            'characters.bunny':{'character':'Easter Bunny'},
            'pro':{},
            'maps.lake_frigid':{'mapType':bsMap.LakeFrigidMap},
            'games.ninja_fight':{'gameType':bsNinjaFight.NinjaFightGame,'previewTex':'courtyardPreview'},
            'games.meteor_shower':{'gameType':bsMeteorShower.MeteorShowerGame,'previewTex':'rampagePreview'},
            'games.target_practice':{'gameType':bsTargetPractice.TargetPracticeGame,'previewTex':'doomShroomPreview'},
            'games.easter_egg_hunt':{'gameType':bsEasterEggHunt.EasterEggHuntGame,'previewTex':'towerDPreview'},
            'icons.flag_us':{'icon':bs.getSpecialChar('flag_us')},
            'icons.flag_mexico':{'icon':bs.getSpecialChar('flag_mexico')},
            'icons.flag_germany':{'icon':bs.getSpecialChar('flag_germany')},
            'icons.flag_brazil':{'icon':bs.getSpecialChar('flag_brazil')},
            'icons.flag_russia':{'icon':bs.getSpecialChar('flag_russia')},
            'icons.flag_china':{'icon':bs.getSpecialChar('flag_china')},
            'icons.flag_uk':{'icon':bs.getSpecialChar('flag_uk')},
            'icons.flag_canada':{'icon':bs.getSpecialChar('flag_canada')},
            'icons.flag_india':{'icon':bs.getSpecialChar('flag_india')},
            'icons.flag_japan':{'icon':bs.getSpecialChar('flag_japan')},
            'icons.flag_france':{'icon':bs.getSpecialChar('flag_france')},
            'icons.flag_indonesia':{'icon':bs.getSpecialChar('flag_indonesia')},
            'icons.flag_italy':{'icon':bs.getSpecialChar('flag_italy')},
            'icons.flag_south_korea':{'icon':bs.getSpecialChar('flag_south_korea')},
            'icons.flag_netherlands':{'icon':bs.getSpecialChar('flag_netherlands')},
            'icons.flag_uae':{'icon':bs.getSpecialChar('flag_uae')},
            'icons.flag_qatar':{'icon':bs.getSpecialChar('flag_qatar')},
            'icons.flag_egypt':{'icon':bs.getSpecialChar('flag_egypt')},
            'icons.flag_kuwait':{'icon':bs.getSpecialChar('flag_kuwait')},
            'icons.flag_algeria':{'icon':bs.getSpecialChar('flag_algeria')},
            'icons.flag_saudi_arabia':{'icon':bs.getSpecialChar('flag_saudi_arabia')},
            'icons.flag_malaysia':{'icon':bs.getSpecialChar('flag_malaysia')},
            'icons.flag_czech_republic':{'icon':bs.getSpecialChar('flag_czech_republic')},
            'icons.flag_australia':{'icon':bs.getSpecialChar('flag_australia')},
            'icons.flag_singapore':{'icon':bs.getSpecialChar('flag_singapore')},
            'icons.fedora':{'icon':bs.getSpecialChar('fedora')},
            'icons.hal':{'icon':bs.getSpecialChar('hal')},
            'icons.crown':{'icon':bs.getSpecialChar('crown')},
            'icons.yinyang':{'icon':bs.getSpecialChar('yinyang')},
            'icons.eyeball':{'icon':bs.getSpecialChar('eyeball')},
            'icons.skull':{'icon':bs.getSpecialChar('skull')},
            'icons.heart':{'icon':bs.getSpecialChar('heart')},
            'icons.dragon':{'icon':bs.getSpecialChar('dragon')},
            'icons.helmet':{'icon':bs.getSpecialChar('helmet')},
            'icons.mushroom':{'icon':bs.getSpecialChar('mushroom')},
            'icons.ninja_star':{'icon':bs.getSpecialChar('ninja_star')},
            'icons.viking_helmet':{'icon':bs.getSpecialChar('viking_helmet')},
            'icons.moon':{'icon':bs.getSpecialChar('moon')},
            'icons.spider':{'icon':bs.getSpecialChar('spider')},
            'icons.fireball':{'icon':bs.getSpecialChar('fireball')},
        }
    return _gStoreItems

# the store layout
def _getStoreLayout():
    global _gStoreLayout
    if _gStoreLayout is None:

        # whats available in the store at a given time; categorized by tab and by section
        _gStoreLayout = {'characters':[{'items':[]}],
                         'extras':[{'items':['pro']}],
                         'maps':[{'items':['maps.lake_frigid']}],
                         'minigames':[],
                         'icons':[{'items':['icons.mushroom','icons.heart','icons.eyeball','icons.yinyang','icons.hal',
                                            'icons.flag_us','icons.flag_mexico','icons.flag_germany','icons.flag_brazil','icons.flag_russia',
                                            'icons.flag_china','icons.flag_uk','icons.flag_canada','icons.flag_india','icons.flag_japan',
                                            'icons.flag_france','icons.flag_indonesia','icons.flag_italy','icons.flag_south_korea','icons.flag_netherlands',
                                            'icons.flag_uae','icons.flag_qatar','icons.flag_egypt','icons.flag_kuwait','icons.flag_algeria',
                                            'icons.flag_saudi_arabia','icons.flag_malaysia','icons.flag_czech_republic','icons.flag_australia','icons.flag_singapore',
                                            'icons.moon','icons.fedora','icons.spider','icons.ninja_star','icons.skull','icons.dragon','icons.viking_helmet','icons.fireball','icons.helmet','icons.crown',
                                            ]}]}
        
    _gStoreLayout['characters'] = [{'items':['characters.kronk','characters.zoe','characters.jackmorgan','characters.mel','characters.snakeshadow',
                                             'characters.bones','characters.bernard','characters.agent',
                                             'characters.frosty','characters.pascal','characters.pixie']}]
    _gStoreLayout['minigames'] = [{'items':['games.ninja_fight','games.meteor_shower','games.target_practice']}]
    if bsInternal._getAccountMiscReadVal('xmas',False):
        _gStoreLayout['characters'][0]['items'].append('characters.santa')
    env = bs.getEnvironment()
    if (env['platform'] == 'android' and env['subplatform'] == 'alibaba'):
        _gStoreLayout['characters'][0]['items'].append('characters.taobaomascot')
    _gStoreLayout['characters'][0]['items'].append('characters.cyborg')
    if bsInternal._getAccountMiscReadVal('easter',False):
        _gStoreLayout['characters'].append({'title':'store.holidaySpecialText','items':['characters.bunny']})
        _gStoreLayout['minigames'].append({'title':'store.holidaySpecialText','items':['games.easter_egg_hunt']})
        
    return _gStoreLayout

_gProSaleStartTime = None

def _getPurchasedIcons():
    if bsInternal._getAccountState() != 'SIGNED_IN': return []
    icons = []
    storeItems = _getStoreItems()
    for itemName,item in storeItems.items():
        if itemName.startswith('icons.') and bsInternal._getPurchased(itemName):
            icons.append(item['icon'])
    return icons
        
def _getAvailableSaleTime(tab):
    try:
        import datetime
        saleTimes = []
        # calc time for our pro sale (old special case)
        proTime = None
        if tab == 'extras':
            config = bs.getConfig()
            if bsUtils._havePro(): return None
            global _gProSaleStartTime
            global _gProSaleStartVal
            # if we havn't calced/loaded start times yet..
            if _gProSaleStartTime is None:

                # if we've got a time-remaining in our config, start there.
                if 'PSTR' in config:
                    _gProSaleStartTime = bs.getRealTime()
                    _gProSaleStartVal = config['PSTR']
                else:

                    # we start the timer once we get the duration from the server
                    startDuration = bsInternal._getAccountMiscReadVal('proSaleDurationMinutes',None)
                    if startDuration is not None:
                        _gProSaleStartTime = bs.getRealTime()
                        _gProSaleStartVal = 60000*startDuration
                    # if we havn't heard from the server yet, no sale..
                    else:
                        return None
                    
            val = max(0,_gProSaleStartVal - (bs.getRealTime()-_gProSaleStartTime))
            
            # keep the value in the config up to date.. i suppose we should write the config
            # occasionally but it should happen often enough for other reasons..
            config['PSTR'] = val
            if val == 0: val = None
            saleTimes.append(val)
        # else:
        #     return None

        # now look for sales in this tab..
        salesRaw = bsInternal._getAccountMiscReadVal('sales',{})
        storeLayout = _getStoreLayout()
        for section in storeLayout[tab]:
            for item in section['items']:
                if item in salesRaw:
                    if not bsInternal._getPurchased(item):
                        toEnd = (datetime.datetime.utcfromtimestamp(salesRaw[item]['e']) - datetime.datetime.utcnow()).total_seconds()
                        if toEnd > 0:
                            saleTimes.append(int(toEnd*1000))
        
        # return the smallest time i guess?..
        return min(saleTimes) if saleTimes else None
        
    except Exception:
        bs.printException('error calcing sale time')
        return None

    

def _getAvailablePurchaseCount(tab=None):
    try:
        if bsInternal._getAccountState() != 'SIGNED_IN': return 0

        count = 0
        ourTickets = bsInternal._getAccountTicketCount()
        storeData = _getStoreLayout()

        if tab is not None: tabs = [(tab,storeData[tab])]
        else: tabs = storeData.items()

        for tabName,tab in tabs:
            if tabName == 'icons': continue # too many of these; don't show..
            for section in tab:
                for item in section['items']:
                    #ticketCost = bsInternal._getAccountMiscReadVal('price.'+item['name'],None)
                    ticketCost = bsInternal._getAccountMiscReadVal('price.'+item,None)
                    if ticketCost is not None:
                        #if ourTickets >= ticketCost and not bsInternal._getPurchased(item['name']):
                        if ourTickets >= ticketCost and not bsInternal._getPurchased(item):
                            count += 1
        return count
    except Exception:
        bs.printException('error calcing available purchases')
        return 0

def doAppInvitesPress(forceCode=False):

    env = bs.getEnvironment()
    doAppInvites = True if (env['platform'] == 'android'
                            and env['subplatform'] == 'google'
                            and bsInternal._getAccountMiscReadVal('enableAppInvites', False)
                            and not env['onTV']) else False
    # doAppInvites = True
    # print 'TEMP DOING APP INV'
    if forceCode: doAppInvites = False

    # FIXME - need to update this to grab a code before allowing the invite UI..
    # doAppInvites = False
    
    if doAppInvites:
        AppInvitesWindow()
    else:
        bs.screenMessage(bs.getResource('gatherWindow.requestingAPromoCodeText'),color=(0,1,0))
        def handleResult(result):
            with bs.Context('UI'):
                if result is None:
                    bs.screenMessage(bs.getResource('errorText'),color=(1,0,0))
                    bs.playSound(bs.getSound('error'))
                else:
                    FriendPromoCodeWindow(result)
        bsInternal._addTransaction({'type':'FRIEND_PROMO_CODE_REQUEST',
                                    'ali': True if (env['platform'] == 'android' and env['subplatform'] == 'alibaba') else False,
                                    'expireTime':time.time()+10},
                                   callback=handleResult)
        bsInternal._runTransactions()

class AppInvitesWindow(Window):
    def __init__(self,origin=(0,0)):

        bsInternal._setAnalyticsScreen('AppInvitesWindow')
        self._data = None
        self._width = 650
        self._height = 400
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              # color=(0.45,0.63,0.15),
                                              transition='inScale',
                                              scale=1.8 if gSmallUI else 1.35 if gMedUI else 1.0)
        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,scale=0.8,position=(60,self._height-50),size=(50,50),
                                             label='',onActivateCall=self.close,autoSelect=True,
                                             #color=(0.45,0.63,0.15),
                                             color=(0.4,0.4,0.6),
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)

        # FIXME - should try this on android tv...
        # if bsUtils.isBrowserLikelyAvailable():
        #     xoffs = 0
        #     env = bs.getEnvironment()
        #     doGoogle = True
        #     if doGoogle: xoffs = -150
        #     # bs.buttonWidget(parent=self._rootWidget,size=(200,40),position=(self._width*0.5-100+xoffs,39),autoSelect=True,
        #     #                 label=bs.getResource('gatherWindow.emailItText'),onActivateCall=bs.WeakCall(self._email))
        #     if doGoogle:

        
        bs.textWidget(parent=self._rootWidget,size=(0,0),position=(self._width*0.5,self._height*0.5+110),autoSelect=True,scale=0.8,
                      maxWidth=self._width*0.9,
                      hAlign='center',vAlign='center',color=(0.3,0.8,0.3),flatness=1.0,
                      text=bs.getResource('gatherWindow.earnTicketsForRecommendingAmountText',
                                          fallback='gatherWindow.earnTicketsForRecommendingText')
                      .replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('friendTryTickets',300)))
                      .replace('${YOU_COUNT}',str(bsInternal._getAccountMiscReadVal('friendTryAwardTickets',100))))
        
        orText = (bs.getResource('orText').replace('${A}','').replace('${B}','')).strip()
        bs.buttonWidget(parent=self._rootWidget,size=(250,150),position=(self._width*0.5-125,self._height*0.5-80),autoSelect=True,buttonType='square',
                        label=bs.getResource('gatherWindow.inviteFriendsText'),onActivateCall=bs.WeakCall(self._googleInvites))

        bs.textWidget(parent=self._rootWidget,size=(0,0),position=(self._width*0.5,self._height*0.5-94),autoSelect=True,scale=0.9,
                      hAlign='center',vAlign='center',color=(0.5,0.5,0.5),flatness=1.0,
                      text=orText)
        
        bs.buttonWidget(parent=self._rootWidget,size=(180,50),position=(self._width*0.5-90,self._height*0.5-170),autoSelect=True,
                        color=(0.5,0.5,0.6),
                        textColor=(0.7,0.7,0.8),
                        textScale=0.8, label=bs.getResource('gatherWindow.appInviteSendACodeText'),onActivateCall=bs.WeakCall(self._sendCode))
                # bs.textWidget(parent=self._rootWidget,size=(0,0),position=(self._width*0.5-xoffs,27),autoSelect=True,scale=0.5,
                #               hAlign='center',vAlign='center',color=(0.3,0.8,0.3),flatness=1.0,
                #               text=bs.getResource('gatherWindow.googlePlayVersionOnlyText'))

        # kick off a transaction to get our code
        env = bs.getEnvironment()
        bsInternal._addTransaction({'type':'FRIEND_PROMO_CODE_REQUEST',
                                    'ali': True if (env['platform'] == 'android' and env['subplatform'] == 'alibaba') else False,
                                    'expireTime':time.time()+20},callback=bs.WeakCall(self._onCodeResult))
        bsInternal._runTransactions()

    def _onCodeResult(self,result):
        if result is not None:
            self._data = result
        
    def _sendCode(self):
        doAppInvitesPress(forceCode=True)
    
    def _googleInvites(self):
        if self._data is None:
            bs.screenMessage(bs.getResource('getTicketsWindow.unavailableTemporarilyText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))
            return

        if bsInternal._getAccountState() == 'SIGNED_IN':
            bsInternal._setAnalyticsScreen('App Invite UI')
            bsInternal._showAppInvite(bs.getResource('gatherWindow.appInviteTitleText').replace('${APP_NAME}',bs.getResource('titleText')),
                                      (bs.getResource('gatherWindow.appInviteMessageText')
                                       .replace('${COUNT}',str(self._data['tickets']))
                                       .replace('${NAME}',bsInternal._getAccountName().split()[0])
                                       .replace('${APP_NAME}',bs.getResource('titleText'))),
                                      self._data['code'])
        else:
            bs.playSound(bs.getSound('error'))
            

    def close(self):
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
class FriendPromoCodeWindow(Window):
        
    def __init__(self,data,origin=(0,0)):

        bsInternal._setAnalyticsScreen('Friend Promo Code')

        env = bs.getEnvironment()
        ali = True if (env['platform'] == 'android' and env['subplatform'] == 'alibaba') else False
        
        self._width = 750 if ali else 650
        self._height = 400
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              color=(0.45,0.63,0.15),
                                              transition='inScale',
                                              scale=1.8 if gSmallUI else 1.35 if gMedUI else 1.0)
        self._data = copy.deepcopy(data)
        bs.playSound(bs.getSound('cashRegister'))
        bs.playSound(bs.getSound('swish'))

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,scale=0.7,position=(40, self._height-(60 if ali else 40)),size=(50,50),
                                             label='',onActivateCall=self.close,autoSelect=True,
                                             color=(0.45,0.63,0.15),
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)

        if ali:
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.3, self._height*0.83), size=(0,0),
                              color=gInfoTextColor,scale=1.0,flatness=1.0,
                              hAlign="center",vAlign="center",
                              text=bs.getResource('gatherWindow.shareThisCodeWithFriendsText'),
                              maxWidth=self._width*0.85)
            
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.3, self._height*0.7), size=(0,0),
                              color=(1.0,3.0,1.0),scale=2.0,
                              hAlign="center",vAlign="center",text=data['code'],maxWidth=self._width*0.4)

            msg = ('\xe4\xbd\xa0\xe7\x9a\x84\xe4\xbb\xbb\xe4\xbd\x95\xe5\xa5\xbd\xe5\x8f\x8b\xe6\xaf\x8f\xe4\xbd\xbf\xe7\x94\xa8\xe4\xb8\x80\xe6\xac\xa1\xef\xbc\x8c\n'
                   '\xe5\xb0\x86\xe5\xbe\x97\xe5\x88\xb0${TICKETS}\xe7\x82\xb9\xe5\x88\xb8\xe5\xa5\x96\xe5\x8a\xb1\xef\xbc\x8c\n'
                   '\xe5\x90\x8c\xe6\x97\xb6\xe4\xbd\xa0\xe5\x8f\xaf\xe6\x94\xb6\xe5\x88\xb0${AWARD_TICKETS}\xe7\x82\xb9\xe5\x88\xb8\xe5\xa5\x96\xe5\x8a\xb1\n'
                   '(\xe6\xad\xa4\xe4\xbb\xa3\xe7\xa0\x81\xe5\x8f\xaa\xe9\x99\x90\xe6\x96\xb0\xe7\x8e\xa9\xe5\xae\xb6\xe4\xbd\xbf\xe7\x94\xa8\xef\xbc\x89\xef\xbc\x8c\n'
                   '\xe4\xbb\xa3\xe7\xa0\x81\xe5\xb0\x86\xe5\x9c\xa8${EXPIRE_HOURS}\xe5\xb0\x8f\xe6\x97\xb6\xe5\x90\x8e\xe5\xa4\xb1\xe6\x95\x88\xe3\x80\x82\n'
                   '\xe5\xbd\x93\xe4\xbd\xbf\xe7\x94\xa8\xe4\xbd\xa0\xe5\x88\x86\xe4\xba\xab\xe7\xa0\x81\xe7\x9a\x84\xe6\x9c\x8b\xe5\x8f\x8b\xe8\xbe\xbe\xe5\x88\xb0${EXTRA_USE_COUNT}\xe4\xba\xba\xe5\x90\x8e\xef\xbc\x8c\n'
                   '\xe4\xbd\xa0\xe5\xb0\x87\xe5\x86\x8d\xe5\xbe\x97\xe5\x88\xb0${EXTRA_TICKETS}\xe7\x82\xb9\xe5\x88\xb8\xe5\xa5\x96\xe5\x8a\xb1\xe3\x80\x82\n'
                   '\xef\xbc\x88\xe5\x9c\xa8\xe2\x80\x9c\xe8\xae\xbe\xe7\xbd\xae\xe2\x86\x92\xe9\xab\x98\xe7\xba\xa7\xe2\x86\x92\xe8\xbe\x93\xe5\x85\xa5\xe4\xbf\x83\xe9\x94\x80\xe4\xbb\xa3\xe7\xa0\x81\xe2\x80\x9d\xe4\xb8\xad\xe4\xbd\xbf\xe7\x94\xa8\xef\xbc\x89')
            msg = msg.replace('${EXPIRE_HOURS}',str(self._data['expireHours']))
            msg = msg.replace('${TICKETS}',str(self._data['tickets']))
            msg = msg.replace('${AWARD_TICKETS}',str(self._data['awardTickets']))
            msg = msg.replace('${EXTRA_USE_COUNT}',str(self._data['extraTicketsUseCount']))
            msg = msg.replace('${EXTRA_TICKETS}',str(self._data['extraTickets']))
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.3,self._height*0.35),size=(0,0),
                              color=gInfoTextColor,scale=1.0,flatness=1.0,
                              hAlign="center",vAlign="center",
                              text=msg,
                              maxWidth=self._width*0.5)
            
            msg = ('\xe8\xaf\xb7\xe7\x94\xa8\xe3\x80\x90\xe5\xbe\xae\xe4\xbf\xa1\xe3\x80\x91\xe6\x88\x96\xe3\x80\x90\xe5\xbe\xae\xe5\x8d\x9a\xe3\x80\x91\xe5\xae\xa2\xe6\x88\xb7\xe7\xab\xaf\n'
                   '\xe6\x89\xab\xe7\xa0\x81\xe5\x88\x86\xe4\xba\xab\xe5\x88\xb0\xe6\x9c\x8b\xe5\x8f\x8b\xe5\x9c\x88\xe6\x88\x96\xe8\xbd\xac\xe5\x8f\x91\xe7\xbb\x99\xe5\xa5\xbd\xe5\x8f\x8b')
                   
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.75,self._height*0.15),size=(0,0),
                              color=gInfoTextColor,scale=0.8,flatness=1.0,
                              hAlign="center",vAlign="center",
                              text=msg,
                              maxWidth=self._width*0.35)

            qrSize = 250
            addr = bsInternal._getAccountMiscReadVal('aliQRFriendURL',"${SERVER}/aqr?c=${CODE}")
            bs.imageWidget(parent=self._rootWidget,position=(self._width * 0.75 - qrSize*0.5,self._height * 0.55 - qrSize * 0.5),size=(qrSize, qrSize),
                           texture=bsInternal._getQRCodeTexture(addr.replace('${SERVER}',bsInternal._getServerAddress()).replace('${CODE}',str(data['code']))))
            
            pass
        else:
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.8),size=(0,0),
                              color=gInfoTextColor,scale=1.0,flatness=1.0,
                              hAlign="center",vAlign="center",
                              text=bs.getResource('gatherWindow.shareThisCodeWithFriendsText'),
                              maxWidth=self._width*0.85)

            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.645),size=(0,0),
                              color=(1.0,3.0,1.0),scale=2.0,
                              hAlign="center",vAlign="center",text=data['code'],maxWidth=self._width*0.85)

            if self._data['awardTickets'] != 0: awardStr = bs.getResource('gatherWindow.friendPromoCodeAwardText').replace('${COUNT}',str(self._data['awardTickets']))
            else: awardStr = ''
            t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.37),size=(0,0),
                              color=gInfoTextColor,scale=1.0,flatness=1.0,
                              hAlign="center",vAlign="center",
                              text=(((bs.getResource('gatherWindow.friendPromoCodeRedeemLongText')
                                     .replace('${COUNT}',str(self._data['tickets']))
                                     .replace('${MAX_USES}',str(self._data['usesRemaining'])))
                                     + '\n'+bs.getResource('gatherWindow.friendPromoCodeWhereToEnterText')
                                    +'\n'+awardStr
                                     +'\n'+bs.getResource('gatherWindow.friendPromoCodeExpireText').replace('${EXPIRE_HOURS}',str(self._data['expireHours'])))),
                              maxWidth=self._width*0.9,maxHeight=self._height*0.35)

        
        
        if bsUtils.isBrowserLikelyAvailable() and not ali:
            xoffs = 0
            # env = bs.getEnvironment()
            #doGoogle = True if (env['platform'] == 'android' and env['subplatform'] == 'google' and bsInternal._getAccountMiscReadVal('enableAppInvites',False)) else False
            # doGoogle = False
            # if doGoogle: xoffs = -150
            bs.buttonWidget(parent=self._rootWidget,size=(200,40),position=(self._width*0.5-100+xoffs,39),autoSelect=True,
                            label=bs.getResource('gatherWindow.emailItText'),onActivateCall=bs.WeakCall(self._email))
            # if doGoogle:
            #     bs.buttonWidget(parent=self._rootWidget,size=(200,40),position=(self._width*0.5-100-xoffs,39),autoSelect=True,
            #                     label=bs.getResource('gatherWindow.sendDirectInvitesText'),onActivateCall=bs.WeakCall(self._googleInvites))
            #     bs.textWidget(parent=self._rootWidget,size=(0,0),position=(self._width*0.5-xoffs,27),autoSelect=True,scale=0.5,
            #                   hAlign='center',vAlign='center',color=(0.3,0.8,0.3),flatness=1.0,
            #                   text=bs.getResource('gatherWindow.googlePlayVersionOnlyText'))

    def _googleInvites(self):
        bsInternal._setAnalyticsScreen('App Invite UI')
        bsInternal._showAppInvite(bs.getResource('gatherWindow.appInviteTitleText').replace('${APP_NAME}',bs.getResource('titleText')),
                                  (bs.getResource('gatherWindow.appInviteMessageText')
                                   .replace('${COUNT}',str(self._data['tickets']))
                                   .replace('${NAME}',bsInternal._getAccountName().split()[0])
                                   .replace('${APP_NAME}',bs.getResource('titleText'))),
                                  self._data['code'])
        
    def _email(self):
        bsInternal._setAnalyticsScreen('Email Friend Code')
        import urllib
        subject = (bs.getResource('gatherWindow.friendHasSentPromoCodeText')
                   .replace('${NAME}',bsInternal._getAccountName())
                   .replace('${APP_NAME}',bs.getResource('titleText'))
                   .replace('${COUNT}',str(self._data['tickets'])))
        body = bs.getResource('gatherWindow.youHaveBeenSentAPromoCodeText').replace('${APP_NAME}',bs.getResource('titleText'))+'\n\n'+str(self._data['code'])+'\n\n'
        body +=((bs.getResource('gatherWindow.friendPromoCodeRedeemShortText')
                 .replace('${COUNT}',str(self._data['tickets'])))
                +'\n\n'+bs.getResource('gatherWindow.friendPromoCodeInstructionsText').replace('${APP_NAME}',bs.getResource('titleText'))
                +'\n'+bs.getResource('gatherWindow.friendPromoCodeExpireText').replace('${EXPIRE_HOURS}',str(self._data['expireHours']))
                +'\n'+bs.getResource('enjoyText'))
        # body += (bs.getResource('gatherWindow.friendPromoCodeInfoText')
        #          .replace('${REDEEM_STR}',
        #                   (bs.getResource('gatherWindow.friendPromoCodeRedeemShortText')
        #                    .replace('${COUNT}',str(self._data['tickets']))
        #                    .replace('${MAX_USES}',str(self._data['usesRemaining']))))
        #          .replace('${AWARD_STR}',awardStr)
        #          .replace('${EXPIRE_HOURS}',str(self._data['expireHours'])))+'\n'+bs.getResource('enjoyText')
        bs.openURL('mailto:?subject='+urllib.quote(bs.utf8(subject))+'&body='+urllib.quote(bs.utf8(body)))
        
        
    def close(self):
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
