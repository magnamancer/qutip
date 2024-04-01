"""
Provide a cython implimentation verner 'most-efficient'
order 7 runge-Kutta method.
See https://www.sfu.ca/~jverner/
"""
# Verner 7 Efficient
# https://www.sfu.ca/~jverner/RKV76.IIa.Efficient.00001675585.081206.CoeffsOnlyFLOAT
__all__ = ["vern7_coeff"]
import numpy as np
order = 7
rk_step = 10
rk_extra_step = 16
denseout_order = 7

bh = np.zeros(rk_step, dtype=np.float64)
a = np.zeros((rk_extra_step, rk_extra_step), dtype=np.float64)
b = np.zeros(rk_step, dtype=np.float64)
c = np.zeros(rk_extra_step, dtype=np.float64)
e = np.zeros(rk_step, dtype=np.float64)
bi = np.zeros((rk_extra_step, denseout_order), dtype=np.float64)

c[0] = 0.
c[1] = .5000000000000000000000000000000000000000e-2
c[2] = .1088888888888888888888888888888888888889
c[3] = .1633333333333333333333333333333333333333
c[4] = .4555000000000000000000000000000000000000
c[5] = .6095094489978381317087004421486024949638
c[6] = .8840000000000000000000000000000000000000
c[7] = .9250000000000000000000000000000000000000
c[8] = 1.
c[9] = 1.

a[1, 0] = .5000000000000000000000000000000000000000e-2

a[2, 0] = -1.076790123456790123456790123456790123457
a[2, 1] = 1.185679012345679012345679012345679012346

a[3, 0] = .4083333333333333333333333333333333333333e-1
a[3, 1] = 0.
a[3, 2] = .1225000000000000000000000000000000000000

a[4, 0] = .6389139236255726780508121615993336109954
a[4, 1] = 0.
a[4, 2] = -2.455672638223656809662640566430653894211
a[4, 3] = 2.272258714598084131611828404831320283215

a[5, 0] = -2.661577375018757131119259297861818119279
a[5, 1] = 0.
a[5, 2] = 10.80451388645613769565396655365532838482
a[5, 3] = -8.353914657396199411968048547819291691541
a[5, 4] = .8204875949566569791420417341743839209619

a[6, 0] = 6.067741434696770992718360183877276714679
a[6, 1] = 0.
a[6, 2] = -24.71127363591108579734203485290746001803
a[6, 3] = 20.42751793078889394045773111748346612697
a[6, 4] = -1.906157978816647150624096784352757010879
a[6, 5] = 1.006172249242068014790040335899474187268

a[7, 0] = 12.05467007625320299509109452892778311648
a[7, 1] = 0.
a[7, 2] = -49.75478495046898932807257615331444758322
a[7, 3] = 41.14288863860467663259698416710157354209
a[7, 4] = -4.461760149974004185641911603484815375051
a[7, 5] = 2.042334822239174959821717077708608543738
a[7, 6] = -0.9834843665406107379530801693870224403537e-1

a[8, 0] = 10.13814652288180787641845141981689030769
a[8, 1] = 0.
a[8, 2] = -42.64113603171750214622846006736635730625
a[8, 3] = 35.76384003992257007135021178023160054034
a[8, 4] = -4.348022840392907653340370296908245943710
a[8, 5] = 2.009862268377035895441943593011827554771
a[8, 6] = .3487490460338272405953822853053145879140
a[8, 7] = -.2714390051048312842371587140910297407572

a[9, 0] = -45.03007203429867712435322405073769635151
a[9, 1] = 0.
a[9, 2] = 187.3272437654588840752418206154201997384
a[9, 3] = -154.0288236935018690596728621034510402582
a[9, 4] = 18.56465306347536233859492332958439136765
a[9, 5] = -7.141809679295078854925420496823551192821
a[9, 6] = 1.308808578161378625114762706007696696508
a[9, 7] = 0.
a[9, 8] = 0.

b[0] = .4715561848627222170431765108838175679569e-1
b[1] = 0.
b[2] = 0.
b[3] = .2575056429843415189596436101037687580986
b[4] = .2621665397741262047713863095764527711129
b[5] = .1521609265673855740323133199165117535523
b[6] = .4939969170032484246907175893227876844296
b[7] = -.2943031171403250441557244744092703429139
b[8] = .8131747232495109999734599440136761892478e-1
b[9] = 0.

bh[0] = .4460860660634117628731817597479197781432e-1
bh[1] = 0.
bh[2] = 0.
bh[3] = .2671640378571372680509102260943837899738
bh[4] = .2201018300177293019979715776650753096323
bh[5] = .2188431703143156830983120833512893824578
bh[6] = .2289871705411202883378173889763552365362
bh[7] = 0.
bh[8] = 0.
bh[9] = .2029518466335628222767054793810430358554e-1

for i in range(10):
    e[i] = b[i] - bh[i]

c[10] = 1

a[10, 0] = .4715561848627222170431765108838175679569e-1
a[10, 1] = 0.
a[10, 2] = 0.
a[10, 3] = .2575056429843415189596436101037687580986
a[10, 4] = .2621665397741262047713863095764527711129
a[10, 5] = .1521609265673855740323133199165117535523
a[10, 6] = .4939969170032484246907175893227876844296
a[10, 7] = -.2943031171403250441557244744092703429139
a[10, 8] = .8131747232495109999734599440136761892478e-1
a[10, 9] = 0.

c[11] = 29/100

a[11, 0] = .5232227691599689815470932256735029887614e-1
a[11, 1] = 0.
a[11, 2] = 0.
a[11, 3] = .2249586182670571550244187743667190903405
a[11, 4] = .1744370924877637539031751304611402542578e-1
a[11, 5] = -.7669379876829393188009028209348812321417e-2
a[11, 6] = .3435896044073284645684381456417912794447e-1
a[11, 7] = -.4102097230093949839125144540100346681769e-1
a[11, 8] = .2565113300520561655297104906598973655221e-1
a[11, 9] = 0.
a[11, 10] = -.1604434570000000000000000000000000000000e-1

c[12] = 1/8

a[12, 0] = .5305334125785908638834747243817578898946e-1
a[12, 1] = 0.
a[12, 2] = 0.
a[12, 3] = .1219530101140188607092225622195251463666
a[12, 4] = .1774684073760249704011573985936092552347e-1
a[12, 5] = -.5928372667681494328907467430302313286925e-3
a[12, 6] = .8381833970853750873624781948796072714855e-2
a[12, 7] = -.1293369259698611956700998079778496462996e-1
a[12, 8] = .9412056815253860804791356641605087829772e-2
a[12, 9] = 0.
a[12, 10] = -.5353253107275676032399320754008272222345e-2
a[12, 11] = -.6666729992455811078380186481263955324311e-1

c[13] = 1/4

a[13, 0] = .3887903257436303686399931060834951327899e-1
a[13, 1] = 0.
a[13, 2] = 0.
a[13, 3] = -.2440320330830131517910045090190069290791e-2
a[13, 4] = -.1392891721467262281273220992320214734208e-2
a[13, 5] = -.4744629155868013465038358934145339168472e-3
a[13, 6] = .3920793241315951369383517310870803393356e-3
a[13, 7] = -.4055473328512800136385880031750264996936e-3
a[13, 8] = .1989709314771672628794304728258886009267e-3
a[13, 9] = 0.
a[13, 10] = -.1027819879317916884712606136811051029682e-3
a[13, 11] = .3385661513870266715302548402957613704604e-1
a[13, 12] = .1814893063199928004309543737509423302792

c[14] = 53/100

a[14, 0] = .5723681204690012909606837582140921695189e-1
a[14, 1] = 0.
a[14, 2] = 0.
a[14, 3] = .2226594806676118099285816235023183680020
a[14, 4] = .1234486420018689904911221497830317287757
a[14, 5] = .4006332526666490875113688731927762275433e-1
a[14, 6] = -.5269894848581452066926326838943832327366e-1
a[14, 7] = .4765971214244522856887315416093212596338e-1
a[14, 8] = -.2138895885042213036387863538386958914368e-1
a[14, 9] = 0.
a[14, 10] = .1519389106403640165459624646184297766866e-1
a[14, 11] = .1206054671628965554251364472502413614358
a[14, 12] = -.2277942301618737288237298052574548913451e-1
a[14, 13] = 0.

c[15] = 79/100

a[15, 0] = .5137203880275681426595607279552927584506e-1
a[15, 1] = 0.
a[15, 2] = 0.
a[15, 3] = .5414214473439405582401399378307410450482
a[15, 4] = .3503998066921840081154745647747846804810
a[15, 5] = .1419311226969218216861835872156617148040
a[15, 6] = .1052737747842942254816302629823570359198
a[15, 7] = -.3108184780587401700842726199589213259835e-1
a[15, 8] = -.7401883149519145061791854716430279714483e-2
a[15, 9] = 0.
a[15, 10] = -.6377932504865363437569726480040013149706e-2
a[15, 11] = -.1732549590836186403386348310205265959935
a[15, 12] = -.1822815677762202619429607513861847306420
a[15, 13] = 0.
a[15, 14] = 0.

bi[0, 0] = 1.
bi[0, 1] = -8.413387198332767469319987751201351965810
bi[0, 2] = 33.67550888449089654479469983556967202215
bi[0, 3] = -70.80159089484886164618905961010838757357
bi[0, 4] = 80.64695108301297872968868805293298389704
bi[0, 5] = -47.19413969837521580145883430419406103536
bi[0, 6] = 11.13381344253924186418881142808952641234

bi[1, 0] = 0.
bi[1, 1] = 0.
bi[1, 2] = 0.
bi[1, 3] = 0.
bi[1, 4] = 0.
bi[1, 5] = 0.
bi[1, 6] = 0.

bi[2, 0] = 0.
bi[2, 1] = 0.
bi[2, 2] = 0.
bi[2, 3] = 0.
bi[2, 4] = 0.
bi[2, 5] = 0.
bi[2, 6] = 0.

bi[3, 0] = 0.
bi[3, 1] = 8.754921980674397160629587282876763437696
bi[3, 2] = -88.45968286997709426134300934922618655402
bi[3, 3] = 346.9017638429916309499891288356321692825
bi[3, 4] = -629.2580030059837046812187141184986252218
bi[3, 5] = 529.6773755604192983874116479833480529304
bi[3, 6] = -167.3588698651401860365089970240284051167

bi[4, 0] = 0.
bi[4, 1] = 8.913387586637921662996190126913331844214
bi[4, 2] = -90.06081846893217794712014609702916991513
bi[4, 3] = 353.1807459217057824951538014683541349020
bi[4, 4] = -640.6476819744374433668701027882567716886
bi[4, 5] = 539.2646279047155261551781390920363285084
bi[4, 6] = -170.3880944299154827945664954924414008798

bi[5, 0] = 0.
bi[5, 1] = 5.173312029847800338889849068990984974299
bi[5, 2] = -52.27111590005538823385270070373176751689
bi[5, 3] = 204.9853867374073094711024260808085419491
bi[5, 4] = -371.8306118563602890875634623992262437796
bi[5, 5] = 312.9880934374529000210073972654145891826
bi[5, 6] = -98.89290352172494693555119599233959305606

bi[6, 0] = 0.
bi[6, 1] = 16.79537744079695986364946329034055578253
bi[6, 2] = -169.7004000005972744435739149730966805754
bi[6, 3] = 665.4937727009246303131700313781960584913
bi[6, 4] = -1207.163889233600728395392916633015853882
bi[6, 5] = 1016.129151581854603280159105697386989470
bi[6, 6] = -321.0600155723749421933210511704882816019

bi[7, 0] = 0.
bi[7, 1] = -10.00599753609866476866352971232058330270
bi[7, 2] = 101.1005433052275068199636113246449312792
bi[7, 3] = -396.4739151237843754958939772727577263768
bi[7, 4] = 719.1787707014182914108130834128646525498
bi[7, 5] = -605.3681033918824350795711030652978269725
bi[7, 6] = 191.2743989279793520691961908384572824802

bi[8, 0] = 0.
bi[8, 1] = 2.764708833638599139713222853969606774131
bi[8, 2] = -27.93460263739046178114640484830267988046
bi[8, 3] = 109.5477918613789217803046856340175757800
bi[8, 4] = -198.7128113064482116421691972646370773711
bi[8, 5] = 167.2663357164031670694252647113936863857
bi[8, 6] = -52.85010499525706346613022509203974406942

bi[9, 0] = 0.
bi[9, 1] = 0.
bi[9, 2] = 0.
bi[9, 3] = 0.
bi[9, 4] = 0.
bi[9, 5] = 0.
bi[9, 6] = 0.

bi[10, 0] = 0.
bi[10, 1] = -2.169632028016350481156919876642428429100
bi[10, 2] = 22.01669603756987625585768587320929912766
bi[10, 3] = -86.90152427798948350846176288615482496306
bi[10, 4] = 159.2238897386147443720253338471077193471
bi[10, 5] = -135.9618306534587908363115231453760181702
bi[10, 6] = 43.79240118328000419804718618785625308759

bi[11, 0] = 0.
bi[11, 1] = -4.890070188793803933769786966428026149549
bi[11, 2] = 22.75407737425176120799532459991506803585
bi[11, 3] = -30.78034218537730965082079824005797506535
bi[11, 4] = -2.797194317207249021142015125037024035537
bi[11, 5] = 31.36945663750840183161406140272783187147
bi[11, 6] = -15.65592732038180043387678567111987465689

bi[12, 0] = 0.
bi[12, 1] = 10.86217092955196715517224349929627754387
bi[12, 2] = -50.54297141782710697188187875653305700081
bi[12, 3] = 68.37148040407511827604242008548181691494
bi[12, 4] = 6.213326521632409162585500428935637861213
bi[12, 5] = -69.68006323194158104163196358466588618336
bi[12, 6] = 34.77605679450919341971367832748521086414

bi[13, 0] = 0.
bi[13, 1] = -11.37286691922922915922346687401389055763
bi[13, 2] = 130.7905807824671644130452602841032046030
bi[13, 3] = -488.6511367778560207543260583489312609826
bi[13, 4] = 832.2148793276440873476229585070779183432
bi[13, 5] = -664.7743368554426242883314487337054193624
bi[13, 6] = 201.7928804424166224412127551654694479565

bi[14, 0] = 0.
bi[14, 1] = -5.919778732715006698693070786679427540601
bi[14, 2] = 63.27679965889218829298274978013773800731
bi[14, 3] = -265.4326820887379575820873554556433306580
bi[14, 4] = 520.1009254140610824835871087519714692468
bi[14, 5] = -467.4121095339020118993777963241667608460
bi[14, 6] = 155.3868452824017054035883640343803117904

bi[15, 0] = 0.
bi[15, 1] = -10.49214619796182281022379415510181241136
bi[15, 2] = 105.3553852518801101042787230303396283676
bi[15, 3] = -409.4397501198893846479834816688367917005
bi[15, 4] = 732.8314489076540326880337353277812147333
bi[15, 5] = -606.3044574733512377981129469949015057785
bi[15, 6] = 188.0495196316683024640077644607192667895

vern7_coeff = {'order': order, 'a': a, 'b': b, 'c': c, 'e': e, 'bi': bi}
