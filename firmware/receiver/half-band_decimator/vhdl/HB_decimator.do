# Library
vlib work

# Module and tb
vcom -work work ./HB_decimator.vhd

# Testbench
vcom -work work ./HB_decimator_tb.vhd

vsim -voptargs="+acc" -t ps work.HB_decimator_tb

add wave HB_decimator_tb/SIM_RUNNING
add wave HB_decimator_tb/uut/*

run -all
