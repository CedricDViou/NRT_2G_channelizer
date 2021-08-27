# logbook

## 2021/08/27

- Final cabling is done
  - Pictures
    - ![pic1](./doc/20210827_105255.jpg)
    - ![pic2](./doc/20210827_105259.jpg)
  - Doc is [here](./doc/20210826_cablage_roach2.odg)
  - Check that PPS are in phase
    - ![screenshot 1](./doc/20210827_101619.jpg)
    - ![screenshot 2](./doc/20210827_101646.jpg)
  - Both ADCs are working now.
- PPS not seen by ADC input hardware
  - Level too low (1V after the splitter)
  - Remove splitter
      - ![picture 1](./doc/20210827_152137.jpg)
      - ![picture 2](./doc/20210827_152145.jpg)

  - PPS only connected on SYNC input of ADC in ZDOK 0
  - Update doc
  - 

## 2021/08/26

- Can program FPGA and Valon
- Can read free running counter
- Can write a & b, and read sum_a_b
- Using adc_and_regs project to get data from ADCs.
  - OK for snapshot0
    - Line at 200 or 250 MHz
    - Can plot FFT
  - KO for snapshot1
    - Data stuck to -128
    - Will open the roach2 case and check connections
      - Only ADC in ZDOk 0 is fed with clk, PPS and Fin...
    - Asking for cabling to be done.


## 2021/08/24

- Generated firmware to test the board
  - cedric@nanunib:/home/cedric/NRT_channelizer/adc_and_regs.slx
  - Compile in 10'


