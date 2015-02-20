<?php

// From https://stackoverflow.com/questions/2915864/php-how-to-find-the-time-elapsed-since-a-date-time

function humanTiming ($time) {
    $time = time() - strtotime($time); // to get the time since that moment
    
    $tokens = array (
        31536000 => 'year',
        2592000 => 'month',
        604800 => 'week',
        86400 => 'day',
        3600 => 'hour',
        60 => 'minute',
        1 => 'second'
    );

    foreach ($tokens as $unit => $text) {
        if ($time < $unit) continue;
        $numberOfUnits = floor($time / $unit);
        return $numberOfUnits.' '.$text.(($numberOfUnits>1)?'s':'');
    }
}

?><!DOCTYPE html>
<html lang="en">
<head>
	<meta charset="utf-8">
	<link href="css/style.css" rel="stylesheet">
	<title>Storj - Team Status</title>
</head>
<body>
<h2>Storj.io Team Status</h2>
	<div class="user-info">
		<div class="user-image">
			<img src="https://s3-us-west-2.amazonaws.com/slack-files2/avatars/2014-08-18/2555802270_72.jpg">
		</div>
		<div class="user-name">
		<a href="ryanaraymond"><span>Ryan Raymond</span></a>
		</div>
		<div class="user-text">Reviewing IEEE template to reformat whitepapers</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-18 21:19:29") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="https://s3-us-west-2.amazonaws.com/slack-files2/avatars/2014-10-27/2879087845_72.jpg">
		</div>
		<div class="user-name">
		<a href="super3"><span>Shawn Wilkinson</span></a>
		</div>
		<div class="user-text">On the road to VC meeting.</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-18 12:55:33") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="https://secure.gravatar.com/avatar/4c0880cd2352fba1f40bde9ebb411e8c.jpg?s=72&amp;d=https%3A%2F%2Fslack.global.ssl.fastly.net%2F8390%2Fimg%2Favatars%2Fava_0007-72.png">
		</div>
		<div class="user-name">
		<a href="frdwrd"><span>James Prestwich</span></a>
		</div>
		<div class="user-text">Working on a blog post: "Why SJCX?"</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-18 04:26:26") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="https://s3-us-west-2.amazonaws.com/slack-files2/avatars/2014-08-19/2555119977_72.jpg">
		</div>
		<div class="user-name">
		<a href="colortwits"><span>Nicola Minichiello</span></a>
		</div>
		<div class="user-text">going through the New Volunteer List, the next team member could be you!</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-18 03:40:00") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="https://secure.gravatar.com/avatar/47ea91e8096f914d22c7eb8d905fe9bf.jpg?s=72&amp;d=https%3A%2F%2Fslack.global.ssl.fastly.net%2F8390%2Fimg%2Favatars%2Fava_0004-72.png">
		</div>
		<div class="user-name">
		<a href="jbrandoff"><span>Josh Brandoff</span></a>
		</div>
		<div class="user-text">writing architecture, road map and contribution documents.</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-18 03:19:25") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="https://s3-us-west-2.amazonaws.com/slack-files2/avatars/2014-11-30/3115599304_64f28699600e088eefa7_72.jpg">
		</div>
		<div class="user-name">
		<a href="none"><span>Tome Boshevski</span></a>
		</div>
		<div class="user-text">Pitch Deck Design</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-17 20:37:50") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="http://www.gravatar.com/avatar/a789aa6e7e867e7f4d3a9dcb9e52b29d?s=72&amp;d=http%3A%2F%2Fstorj.sdo-srv.com%2Fstorjlogo.jpg">
		</div>
		<div class="user-name">
		<a href="subwolf"><span>Robin Beckett</span></a>
		</div>
		<div class="user-text">Playing with bot code.</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-14 20:20:17") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="http://www.gravatar.com/avatar/d36605007c3afb6ec8f238fe8c562db3?s=72&amp;d=http%3A%2F%2Fstorj.sdo-srv.com%2Fstorjlogo.jpg">
		</div>
		<div class="user-name">
		<a href="robamichael"><span>Rob Michael</span></a>
		</div>
		<div class="user-text">back to reviewing marketing plan 2015 on Monday</div>
		<div class="user-date">
		<?php echo humanTiming("2015-02-02 04:12:18") . " ago"; ?>
		</div>
	</div>
 <div class="user-info">
		<div class="user-image">
			<img src="https://secure.gravatar.com/avatar/363b8868efcc8afa9859628b55ebaaa2.jpg?s=72&amp;d=https%3A%2F%2Fslack.global.ssl.fastly.net%2F8390%2Fimg%2Favatars%2Fava_0020-72.png">
		</div>
		<div class="user-name">
		<a href="switchpwn"><span>Mustafa Gezen</span></a>
		</div>
		<div class="user-text">Working on DriveShare GUI</div>
		<div class="user-date">
		<?php echo humanTiming("2014-12-31 19:04:52") . " ago"; ?>
		</div>
	</div>
</body>
</html>

