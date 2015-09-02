import bs
import bsUI
import time
import bsInternal
import copy
import bsUtils


class LinkAccountsWindow(bsUI.Window):

    def __init__(self,transition='inRight',originWidget=None):
        if originWidget is not None:
            self._transitionOut = 'outScale'
            scaleOrigin = originWidget.getScreenSpaceCenter()
            transition = 'inScale'
        else:
            self._transitionOut = 'outRight'
            scaleOrigin = None
            transition = 'inRight'
        bgColor = (0.4,0.4,0.5)
        self._width = 540
        self._height = 330
        baseScale=2.0 if bsUI.gSmallUI else 1.6 if bsUI.gMedUI else 1.1
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),transition=transition,scale=baseScale,
                                              scaleOriginStackOffset=scaleOrigin,
                                              stackOffset=(0,-10) if bsUI.gSmallUI else (0,0))
        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._cancel,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.57),size=(0,0),
                      text=bs.getResource('accountSettingsWindow.linkAccountsInstructionsText').replace('${COUNT}',str(bsInternal._getAccountMiscReadVal('maxLinkAccounts',5))),
                      maxWidth=self._width*0.9,
                      color=bsUI.gInfoTextColor,
                      maxHeight=self._height*0.6,hAlign='center',vAlign='center')
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)
        bs.buttonWidget(parent=self._rootWidget,position=(40,30),size=(200,60),
                        label=bs.getResource('accountSettingsWindow.linkAccountsGenerateCodeText'),autoSelect=True,
                        onActivateCall=self._generatePress)
        self._enterCodeButton = bs.buttonWidget(parent=self._rootWidget,position=(self._width-240,30),size=(200,60),
                                                label=bs.getResource('accountSettingsWindow.linkAccountsEnterCodeText'),autoSelect=True,
                                                onActivateCall=self._enterCodePress)
    def _generatePress(self):
        if bsInternal._getAccountState() != 'SIGNED_IN':
            bsUI.showSignInPrompt()
            return
        bs.screenMessage(bs.getResource('gatherWindow.requestingAPromoCodeText'),color=(0,1,0))
        bsInternal._addTransaction({'type':'ACCOUNT_LINK_CODE_REQUEST',
                                    'expireTime':time.time()+5})
        bsInternal._runTransactions()

    def _enterCodePress(self):
        bsUI.PromoCodeWindow(modal=True,originWidget=self._enterCodeButton)
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)
        
    def _cancel(self):
        bs.containerWidget(edit=self._rootWidget,transition=self._transitionOut)

def _handleUIRemotePress():
    #dCount = bsInternal._getLocalActiveInputDevicesCount()
    env = bs.getEnvironment()
    if env['onTV'] and (env['platform'] == 'android' and env['subplatform'] == 'alibaba'):
        GetBSRemoteWindow()
    else:
        bs.screenMessage(bs.getResource("internal.controllerForMenusOnlyText"),color=(1,0,0))
        bs.playSound(bs.getSound('error'))
    
class GetBSRemoteWindow(bsUI.PopupWindow):

    def __init__(self):

        # position=originWidget.getScreenSpaceCenter()
        position=(0,0)
        
        scale = 2.3 if bsUI.gSmallUI else 1.65 if bsUI.gMedUI else 1.23
        self._transitioningOut = False
        
        self._width = 570
        self._height = 350

        bgColor = (0.5,0.4,0.6)
        
        bsUI.PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                             scale=scale,bgColor=bgColor)

        env = bs.getEnvironment()

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(50,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=bgColor,
                                             onActivateCall=self._onCancelPress,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)

        env = bs.getEnvironment()
        if (env['platform'] == 'android' and env['subplatform'] == 'alibaba'):
            txt = ('\xe8\xbf\x99\xe6\x98\xaf\xe4\xb8\x80\xe4\xb8\xaa\xe5\x8f\xaf\xe4\xbb\xa5\xe5\x92\x8c\xe5\xae\xb6\xe4\xba\xba\xe6\x9c\x8b\xe5\x8f\x8b\xe4\xb8\x80\xe8\xb5\xb7\xe7\x8e\xa9\xe7\x9a\x84\xe6\xb8\xb8\xe6\x88\x8f,\xe5\x90\x8c\xe6\x97\xb6\xe6\x94\xaf\xe6\x8c\x81\xe8\x81\x94 \xe2\x80\xa8\xe7\xbd\x91\xe5\xaf\xb9\xe6\x88\x98\xe3\x80\x82\n'
                   '\xe5\xa6\x82\xe6\xb2\xa1\xe6\x9c\x89\xe6\xb8\xb8\xe6\x88\x8f\xe6\x89\x8b\xe6\x9f\x84,\xe5\x8f\xaf\xe4\xbb\xa5\xe4\xbd\xbf\xe7\x94\xa8\xe7\xa7\xbb\xe5\x8a\xa8\xe8\xae\xbe\xe5\xa4\x87\xe6\x89\xab\xe7\xa0\x81\xe4\xb8\x8b\xe8\xbd\xbd\xe2\x80\x9c\xe9\x98\xbf\xe9\x87\x8c\xc2\xa0TV\xc2\xa0\xe5\x8a\xa9\xe6\x89\x8b\xe2\x80\x9d\xe7\x94\xa8 \xe6\x9d\xa5\xe4\xbb\xa3\xe6\x9b\xbf\xe5\xa4\x96\xe8\xae\xbe\xe3\x80\x82\n'
                   '\xe6\x9c\x80\xe5\xa4\x9a\xe6\x94\xaf\xe6\x8c\x81\xe6\x8e\xa5\xe5\x85\xa5\xc2\xa08\xc2\xa0\xe4\xb8\xaa\xe5\xa4\x96\xe8\xae\xbe')
            bs.textWidget(parent=self._rootWidget, size=(0,0), hAlign='center', vAlign='center', maxWidth = self._width * 0.9,
                          position=(self._width*0.5, 60), text=txt)
            bs.imageWidget(parent=self._rootWidget, position=(self._width - 260, self._height*0.63-100), size=(200, 200),
                           texture=bs.getTexture('aliControllerQR'))
            bs.imageWidget(parent=self._rootWidget, position=(40, self._height*0.58-100), size=(230, 230),
                           texture=bs.getTexture('multiplayerExamples'))
        else:
            bs.imageWidget(parent=self._rootWidget, position=(self._width*0.5-110, self._height*0.67-110), size=(220, 220),
                           texture=bs.getTexture('multiplayerExamples'))
            bs.textWidget(parent=self._rootWidget, size=(0,0), hAlign='center', vAlign='center', maxWidth = self._width * 0.9,
                          position=(self._width*0.5, 60), text=bs.getResource('remoteAppInfoShortText').replace('${APP_NAME}',bs.getResource('titleText')).replace('${REMOTE_APP_NAME}',bs.getResource('remote_app.app_name')))
            pass
        # bs.imageWidget(parent=self._rootWidget, position=(self._width*0.5-150, self._height*0.5-150), size=(300, 300),
        #                texture=qrTex)
        
    def _onCancelPress(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            bs.containerWidget(edit=self._rootWidget,transition='outScale')

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._transitionOut()
        
class ChallengeEntryWindow(bsUI.PopupWindow):

    def __init__(self,challengeID,challengeActivity=None,position=(0,0),delegate=None,scale=None,offset=(0,0),onCloseCall=None):

        self._challengeID = challengeID

        self._onCloseCall = onCloseCall
        if scale is None: scale = 2.3 if bsUI.gSmallUI else 1.65 if bsUI.gMedUI else 1.23
        self._delegate = delegate
        self._transitioningOut = False

        self._challengeActivity = challengeActivity
        
        self._width = 340
        self._height = 290

        self._canForfeit = False
        self._forfeitButton = None

        challenge = bsUI._getCachedChallenge(self._challengeID)
        # this stuff shouldn't change..
        if challenge is None:
            self._canForfeit = False
            self._prizeTickets = 0
            self._prizeTrophy = None
            self._level = 0
            self._waitTickets = 0
        else:
            self._canForfeit = challenge['canForfeit']
            self._prizeTrophy = challenge['prizeTrophy']
            self._prizeTickets = challenge['prizeTickets']
            self._level = challenge['level']
            t = time.time()
            self._waitTickets = max(1,int(challenge['waitTickets'] * (1.0 - (t-challenge['waitStart'])/(challenge['waitEnd']-challenge['waitStart']))))
            
        
        self._bgColor = (0.5,0.4,0.6)
        
        # creates our _rootWidget
        bsUI.PopupWindow.__init__(self,position=position,size=(self._width,self._height),
                                  scale=scale,bgColor=self._bgColor,offset=offset)
        self._state = None
        self._updateTimer = bs.Timer(1000,bs.WeakCall(self._update),repeat=True,timeType='real')
        self._update()

    def _rebuildForState(self,newState):

        if self._state is not None:
            self._saveState()
        
        # clear out previous state (if any)
        children = self._rootWidget.getChildren()
        for c in children: c.delete()

        self._state = newState
        
        # print 'REBUILDING FOR STATE',self._state
        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(20,self._height-30),size=(50,50),scale=0.5,
                                             label='',color=self._bgColor,
                                             onActivateCall=self._onCancel,autoSelect=True,
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        titleScale = 0.6
        titleColor = (1,1,1,0.4)
        showPrizes = False
        showLevel = False
        showForfeitButton = False
        
        if self._state == 'error':
            titleStr = bs.getResource('coopSelectWindow.challengesText')
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5),size=(0,0),hAlign='center',vAlign='center',
                          scale=0.7,text=bs.getResource('errorText'),maxWidth=self._width*0.8)
        elif self._state == 'skipWaitNextChallenge':
            titleStr = bs.getResource('coopSelectWindow.nextChallengeText')
            #showLevel = True
            bWidth = 140
            bHeight = 130
            imgWidth = 80
            imgHeight = 80
            bPos = (self._width*0.5,self._height*0.52)
            b = bs.buttonWidget(parent=self._rootWidget,position=(bPos[0]-bWidth*0.5,bPos[1]-bHeight*0.5),
                                onActivateCall=bs.WeakCall(self._load),
                                label='',size=(bWidth,bHeight),buttonType='square',autoSelect=True)
            bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            bs.textWidget(parent=self._rootWidget,drawController=b,hAlign='center',vAlign='center',
                          text=bs.getResource('coopSelectWindow.skipWaitText'),
                          size=(0,0),maxWidth=bWidth*0.8,
                          color=(0.75,1.0,0.7),position=(bPos[0],bPos[1]-bHeight*0.0),scale=0.9)
            bs.textWidget(parent=self._rootWidget,drawController=b,hAlign='center',vAlign='center',
                          text=bs.getSpecialChar('ticket')+str(self._waitTickets),size=(0,0),scale=0.6,
                          color=(1,0.5,0),position=(bPos[0],bPos[1]-bHeight*0.23))
            # bs.imageWidget(parent=self._rootWidget,drawController=b,size=(80,80),
            #                position=(bPos[0]-imgWidth*0.5,bPos[1]-imgHeight*0.5),texture=bs.getTexture('tickets'))
            #showPrizes = True
        elif self._state == 'skipWaitNextPlay':
            showLevel = True
            showForfeitButton = True
            bWidth = 140
            bHeight = 130
            imgWidth = 80
            imgHeight = 80
            bPos = (self._width*0.5,self._height*0.52)
            b = bs.buttonWidget(parent=self._rootWidget,position=(bPos[0]-bWidth*0.5,bPos[1]-bHeight*0.5),
                                onActivateCall=bs.WeakCall(self._play),
                                label='',size=(bWidth,bHeight),buttonType='square',autoSelect=True)
            bs.widget(edit=b,upWidget=self._cancelButton)
            bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            bs.textWidget(parent=self._rootWidget,drawController=b,hAlign='center',vAlign='center',
                          text=bs.getResource('coopSelectWindow.playNowText'),size=(0,0),maxWidth=bWidth*0.8,
                          color=(0.75,1.0,0.7),position=(bPos[0],bPos[1]-bHeight*0.0),scale=0.9)
            bs.textWidget(parent=self._rootWidget,drawController=b,hAlign='center',vAlign='center',
                          text=bs.getSpecialChar('ticket')+str(self._waitTickets),size=(0,0),scale=0.6,
                          color=(1,0.5,0),position=(bPos[0],bPos[1]-bHeight*0.23))
            # bs.imageWidget(parent=self._rootWidget,drawController=b,size=(80,80),
            #                position=(bPos[0]-imgWidth*0.5,bPos[1]-imgHeight*0.5),texture=bs.getTexture('tickets'))
            showPrizes = True
            
        elif self._state == 'freePlay':
            showLevel = True
            showForfeitButton = True
            bWidth = 140
            bHeight = 130
            b = bs.buttonWidget(parent=self._rootWidget,position=(self._width*0.5-bWidth*0.5,self._height*0.52-bHeight*0.5),
                                onActivateCall=bs.WeakCall(self._play),
                                label=bs.getResource('playText'),size=(bWidth,bHeight),buttonType='square',autoSelect=True)
            bs.widget(edit=b,upWidget=self._cancelButton)
            bs.containerWidget(edit=self._rootWidget,selectedChild=b)
            showPrizes = True
        elif self._state == 'ended':
            titleStr = bs.getResource('coopSelectWindow.challengesText')
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5),size=(0,0),hAlign='center',vAlign='center',
                          scale=0.7,text=bs.getResource('challengeEndedText'),maxWidth=self._width*0.8)
        else:
            titleStr = ''
            print 'Unrecognized state for ChallengeEntryWindow:',self._state
        
        if showLevel:
            titleColor = (1,1,1,0.7)
            titleStr = 'Meteor Shower Blah'
            titleScale = 0.7
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.86),
                          size=(0,0),hAlign='center',vAlign='center',color=(0.8,0.8,0.4,0.7),
                          flatness=1.0,scale=0.55,text=bs.getResource('levelText').replace('${NUMBER}',str(self._level)),maxWidth=self._width*0.8)

        self._titleText = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height-20),size=(0,0),hAlign='center',vAlign='center',
                                        scale=titleScale,text=titleStr,maxWidth=200,color=titleColor)

        if showForfeitButton:
            bWidth = 40
            bHeight = 25
            self._forfeitButton = bs.buttonWidget(parent=self._rootWidget,position=(self._width-bWidth-16,self._height-bHeight-10),
                                                  label=bs.getResource('coopSelectWindow.forfeitText'),size=(bWidth,bHeight),buttonType='square',
                                                  color=(0.6,0.45,0.6),
                                                  onActivateCall=bs.WeakCall(self._onForfeitPress),
                                                  textColor=(0.65,0.55,0.65),
                                                  autoSelect=True)
        else: self._forfeitButton = None
            
        if showPrizes:
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.24),size=(0,0),hAlign='center',vAlign='center',
                          flatness=1.0,scale=0.6,text=bs.getResource('coopSelectWindow.prizesText'),maxWidth=self._width*0.8,color=(0.8,0.8,1,0.5)),
            prizes = []
            if self._prizeTrophy is not None: prizes.append(bs.getSpecialChar('trophy'+str(self._prizeTrophy)))
            if self._prizeTickets != 0: prizes.append(bs.getSpecialChar('ticketBacking')+str(self._prizeTickets))
            bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.13),size=(0,0),hAlign='center',vAlign='center',
                          scale=0.8,flatness=1.0,color=(0.7,0.7,0.7,1),
                          text='   '.join(prizes),maxWidth=self._width*0.8)

        self._restoreState()
            
    def _load(self):
        self._transitionOut()
        bs.screenMessage("WOULD LOAD CHALLENGE: "+self._challengeID,color=(0,1,0))
        
    def _play(self):
        self._transitionOut()
        bs.screenMessage("WOULD PLAY CHALLENGE: "+self._challengeID,color=(0,1,0))

    def _onForfeitPress(self):
        if self._canForfeit:
            bsUI.ConfirmWindow(bs.getResource('coopSelectWindow.forfeitConfirmText'),
                               bs.WeakCall(self._forfeit),originWidget=self._forfeitButton,
                               width=400,height=120)
        else:
            bs.screenMessage(bs.getResource('coopSelectWindow.forfeitNotAllowedYetText'),color=(1,0,0))
            bs.playSound(bs.getSound('error'))

    def _forfeit(self):
        self._transitionOut()
        bs.screenMessage("WOULD FORFEIT CHALLENGE: "+self._challengeID,color=(0,1,0))
        
    def _update(self):
        # print 'UPDATE',bs.getRealTime()

        # figure out what our state should be based on our current cached challenge data
        challenge = bsUI._getCachedChallenge(self._challengeID)
        if challenge is None: newState = 'error'
        elif challenge['end'] <= time.time(): newState = 'ended'
        elif challenge['waitEnd'] > time.time():
            if challenge['waitType'] == 'nextChallenge': newState = 'skipWaitNextChallenge'
            else: newState = 'skipWaitNextPlay'
        else:
            newState = 'freePlay'

        # if our state is changing, rebuild..
        if self._state != newState:
            self._rebuildForState(newState)

        if self._forfeitButton is not None:
            bs.buttonWidget(edit=self._forfeitButton,
                            color=(0.6,0.45,0.6) if self._canForfeit else (0.6,0.57,0.6),
                            textColor=(0.65,0.55,0.65) if self._canForfeit else (0.5,0.5,0.5))
        
            
        
    def _onCancel(self):
        self._transitionOut()
        
    def _transitionOut(self):
        if not self._transitioningOut:
            self._transitioningOut = True
            self._saveState()
            bs.containerWidget(edit=self._rootWidget,transition='outScale')
            if self._onCloseCall is not None:
                self._onCloseCall()

    def onPopupCancel(self):
        bs.playSound(bs.getSound('swish'))
        self._onCancel()

    def _saveState(self):
        # print 'saving state'
        #sel = self._rootWidget.getSelectedChild()
        # if sel == self._payWithAdButton: selName = 'Ad'
        pass
        #sel = self._rootWidget.getSelectedChild()
        # if sel == self._payWithAdButton: selName = 'Ad'
        # else: selName = 'Tickets'
        #bs.getConfig()['Challenge Pay Selection'] = selName
        #bs.writeConfig()
    
    def _restoreState(self):
        # print 'restoring state'
        pass
        # try: selName = bs.getConfig()['Tournament Pay Selection']
        # except Exception: selName = 'Tickets'
        # if selName == 'Ad' and self._payWithAdButton is not None: sel = self._payWithAdButton
        # else: sel = self._payWithTicketsButton
        # bs.containerWidget(edit=self._rootWidget,selectedChild=sel)


class AccountLinkCodeWindow(bsUI.Window):
        
    def __init__(self,data):
        self._width = 350
        self._height = 200
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              color=(0.45,0.63,0.15),
                                              transition='inScale',
                                              scale=1.8 if bsUI.gSmallUI else 1.35 if bsUI.gMedUI else 1.0)
        self._data = copy.deepcopy(data)
        bs.playSound(bs.getSound('cashRegister'))
        bs.playSound(bs.getSound('swish'))

        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,scale=0.5,position=(40,self._height-40),size=(50,50),
                                             label='',onActivateCall=self.close,autoSelect=True,
                                             color=(0.45,0.63,0.15),
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)
        
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.5),size=(0,0),
                          color=(1.0,3.0,1.0),scale=2.0,
                          hAlign="center",vAlign="center",text=data['code'],maxWidth=self._width*0.85)
    def close(self):
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
class ServerDialogWindow(bsUI.Window):
        
    def __init__(self,data):

        self._dialogID = data['dialogID']
        txt = bs.translate('serverResponses',data['text'])
        if 'subs' in data:
            for sub in data['subs']: txt = txt.replace(sub[0],sub[1])
        txt = txt.strip()
        txtScale = 1.5
        txtHeight = bs.getStringHeight(txt) * txtScale
        self._width = 500
        self._height = 130+min(200,txtHeight)
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              #color=(0.45,0.63,0.15),
                                              transition='inScale',
                                              scale=1.8 if bsUI.gSmallUI else 1.35 if bsUI.gMedUI else 1.0)
        self._startTime = bs.getRealTime()

        bs.playSound(bs.getSound('swish'))
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,70+(self._height-70)*0.5),size=(0,0),
                          color=(1.0,3.0,1.0),scale=txtScale,
                          hAlign="center",vAlign="center",
                          text=txt,
                          maxWidth=self._width*0.85,
                          maxHeight=(self._height-110))
        showCancel = data.get('showCancel',True)
        if showCancel:
            self._cancelButton = bs.buttonWidget(parent=self._rootWidget,position=(30,30),size=(160,60),
                                                 autoSelect=True,label=bs.getResource('cancelText'),
                                                 onActivateCall=self._cancelPress)
        else:
            self._cancelButton = None
        self._okButton = bs.buttonWidget(parent=self._rootWidget,position=((self._width-182) if showCancel else (self._width*0.5-80),30),size=(160,60),
                                             autoSelect=True,label=bs.getResource('okText'),
                                         onActivateCall=self._okPress)
        bs.containerWidget(edit=self._rootWidget,
                           cancelButton=self._cancelButton,
                           startButton=self._okButton,
                           selectedChild=self._okButton)

    def _okPress(self):
        if bs.getRealTime()-self._startTime < 1000:
            bs.playSound(bs.getSound('error'))
            return
        bsInternal._addTransaction({'type':'DIALOG_RESPONSE','dialogID':self._dialogID,'response':1})
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
    def _cancelPress(self):
        if bs.getRealTime()-self._startTime < 1000:
            bs.playSound(bs.getSound('error'))
            return
        bsInternal._addTransaction({'type':'DIALOG_RESPONSE','dialogID':self._dialogID,'response':0})
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
        
class ReportPlayerWindow(bsUI.Window):
        
    def __init__(self,accountID,originWidget):
        self._width = 550
        self._height = 220
        self._accountID = accountID
        self._transitionOut = 'outScale'
        scaleOrigin = originWidget.getScreenSpaceCenter()
        transition = 'inScale'
        
        self._rootWidget = bs.containerWidget(size=(self._width,self._height),
                                              transition='inScale',
                                              scaleOriginStackOffset=scaleOrigin,
                                              scale=1.8 if bsUI.gSmallUI else 1.35 if bsUI.gMedUI else 1.0)
        self._cancelButton = bs.buttonWidget(parent=self._rootWidget,scale=0.7,position=(40,self._height-50),
                                             size=(50,50),
                                             label='',onActivateCall=self.close,autoSelect=True,
                                             color=(0.4,0.4,0.5),
                                             icon=bs.getTexture('crossOut'),iconScale=1.2)
        bs.containerWidget(edit=self._rootWidget,cancelButton=self._cancelButton)
        
        t = bs.textWidget(parent=self._rootWidget,position=(self._width*0.5,self._height*0.64),size=(0,0),
                          color=(1,1,1,0.8),scale=1.2,
                          hAlign="center",vAlign="center",
                          text=bs.getResource('reportThisPlayerReasonText'),
                          maxWidth=self._width*0.85)
        bs.buttonWidget(parent=self._rootWidget,size=(235,60),position=(20,30),label=bs.getResource('reportThisPlayerLanguageText'),
                        onActivateCall=self._onLanguagePress,autoSelect=True)
        bs.buttonWidget(parent=self._rootWidget,size=(235,60),position=(self._width-255,30),label=bs.getResource('reportThisPlayerCheatingText'),
                        onActivateCall=self._onCheatingPress,autoSelect=True)

    def _onLanguagePress(self):
        bsInternal._addTransaction({'type':'REPORT_ACCOUNT',
                                    'reason':'language',
                                    'account':self._accountID})
        import urllib
        body = bs.getResource('reportPlayerExplanationText')
        bs.openURL('mailto:support@froemling.net?subject=BombSquad Player Report: '+self._accountID+'&body='+urllib.quote(bs.utf8(body)))
        self.close()

    def _onCheatingPress(self):
        bsInternal._addTransaction({'type':'REPORT_ACCOUNT',
                                    'reason':'cheating',
                                    'account':self._accountID})
        import urllib
        body = bs.getResource('reportPlayerExplanationText')
        bs.openURL('mailto:support@froemling.net?subject=BombSquad Player Report: '+self._accountID+'&body='+urllib.quote(bs.utf8(body)))
        self.close()
        
    def close(self):
        bs.containerWidget(edit=self._rootWidget,transition='outScale')
