# Library
vlib work

# Module and tb
vcom -work work ./HB_decimator.vhd

# Testbench
vcom -work work ./HB_decimator_tb.vhd

vsim -voptargs="+acc" -t ps work.HB_decimator_tb

add wave -noupdate -group AllSignals HB_decimator_tb/SIM_RUNNING
add wave -noupdate -group AllSignals HB_decimator_tb/uut/*

add wave -noupdate /hb_decimator_tb/uut/rst
add wave -noupdate /hb_decimator_tb/uut/clk
add wave -noupdate /hb_decimator_tb/uut/sync_in
add wave -noupdate /hb_decimator_tb/uut/sync_out
add wave -noupdate /hb_decimator_tb/uut/data_in_valid
add wave -noupdate -childformat {{/hb_decimator_tb/uut/data_in(0) -radix decimal}} -expand -subitemconfig {/hb_decimator_tb/uut/data_in(0) {-format Analog-Step -height 100 -max 66000.0 -min -1000.0 -radix decimal}} /hb_decimator_tb/uut/data_in

add wave -noupdate -childformat {{/hb_decimator_tb/uut/data_in(0) -radix decimal}} -expand -subitemconfig {/hb_decimator_tb/uut/data_in(0) {-format Analog-Step -height 100 -max 66000.0 -min -1000.0 -radix decimal}} /hb_decimator_tb/uut/data_in

add wave -noupdate /hb_decimator_tb/uut/data_out_valid
add wave -noupdate -childformat {{/hb_decimator_tb/uut/data_out(0) -radix decimal}} -expand -subitemconfig {/hb_decimator_tb/uut/data_out(0) {-format Analog-Step -height 100 -max 66000.0 -min -1000.0 -radix decimal}} /hb_decimator_tb/uut/data_out


run -all
